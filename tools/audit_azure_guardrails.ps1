param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resourceGroup = "rg-jarvis-os-cloud"
$containerApp = "jarvis-os-planner"
$budgetName = "jarvis-os"
$deploymentAppName = "jarvis-os-github-deploy"
$expectedSubscriptionName = "Azure subscription 1"
$expectedRepository = "JarvisOS"
$runtimePath = Join-Path ([IO.Path]::GetFullPath($ProjectRoot)) "runtime"
$logPath = Join-Path $runtimePath "azure_guardrail_audit.jsonl"
$previousLogPath = "$logPath.previous"
$failures = [Collections.Generic.List[string]]::new()
$currentStage = "startup"

function Add-AuditFailure {
    param([string]$Code)
    if (-not $script:failures.Contains($Code)) {
        $script:failures.Add($Code)
    }
}

function Assert-AuditCondition {
    param(
        [bool]$Condition,
        [string]$FailureCode
    )
    if (-not $Condition) {
        Add-AuditFailure -Code $FailureCode
    }
}

function Invoke-AzJson {
    param([string[]]$Arguments)
    $raw = & $script:azPath @Arguments --only-show-errors --output json 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "azure_cli_request_failed"
    }
    $text = $raw -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "azure_cli_empty_response"
    }
    $parsed = $text | ConvertFrom-Json
    if ($parsed -is [Array]) {
        foreach ($item in $parsed) {
            Write-Output $item
        }
        return
    }
    return $parsed
}

function Test-ExactRole {
    param(
        [object[]]$Assignments,
        [string]$PrincipalId,
        [string]$RoleName,
        [string]$Scope
    )
    $matches = @(
        $Assignments | Where-Object {
            ([string]$_.principalId).ToLowerInvariant() -eq
                $PrincipalId.ToLowerInvariant() -and
            $_.roleDefinitionName -eq $RoleName -and
            ([string]$_.scope).ToLowerInvariant() -eq
                $Scope.ToLowerInvariant()
        }
    )
    return $matches.Count -eq 1
}

function Write-SafeAuditResult {
    param([hashtable]$Result)
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    if (
        (Test-Path -LiteralPath $logPath -PathType Leaf) -and
        (Get-Item -LiteralPath $logPath).Length -ge 524288
    ) {
        Move-Item -LiteralPath $logPath -Destination $previousLogPath -Force
    }
    $line = $Result | ConvertTo-Json -Compress
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Output $line
}

try {
    $currentStage = "azure_login"
    $azCommand = Get-Command az -ErrorAction Stop
    $script:azPath = $azCommand.Source

    $account = Invoke-AzJson -Arguments @(
        "account", "show",
        "--query", "{id:id,name:name}"
    )
    Assert-AuditCondition (
        $account.name -eq $expectedSubscriptionName
    ) "wrong_subscription"

    $currentStage = "container_app"
    $app = Invoke-AzJson -Arguments @(
        "containerapp", "show",
        "--name", $containerApp,
        "--resource-group", $resourceGroup,
        "--query",
        "{id:id,principalId:identity.principalId,fqdn:properties.configuration.ingress.fqdn,storage:properties.template.containers[0].env[?name=='JARVIS_OS_REMOTE_STORAGE_ACCOUNT'].value,buildSha:properties.template.containers[0].env[?name=='JARVIS_OS_BUILD_SHA'].value}"
    )
    $storageAccountName = [string]@($app.storage)[0]
    $deployedBuildSha = [string]@($app.buildSha)[0]
    Assert-AuditCondition (
        -not [string]::IsNullOrWhiteSpace([string]$app.principalId)
    ) "managed_identity_missing"
    Assert-AuditCondition (
        $deployedBuildSha -match "^[0-9a-f]{40}$"
    ) "immutable_build_missing"

    $currentStage = "authentication"
    $auth = Invoke-AzJson -Arguments @(
        "containerapp", "auth", "show",
        "--name", $containerApp,
        "--resource-group", $resourceGroup,
        "--query",
        "{enabled:platform.enabled,https:httpSettings.requireHttps,owner:identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy.allowedPrincipals.identities[0]}"
    )
    Assert-AuditCondition ($auth.enabled -eq $true) "easyauth_disabled"
    Assert-AuditCondition ($auth.https -eq $true) "easyauth_https_disabled"
    Assert-AuditCondition (
        -not [string]::IsNullOrWhiteSpace([string]$auth.owner)
    ) "phone_owner_missing"

    $currentStage = "storage"
    $storage = Invoke-AzJson -Arguments @(
        "storage", "account", "show",
        "--name", $storageAccountName,
        "--resource-group", $resourceGroup,
        "--query",
        "{id:id,allowSharedKeyAccess:allowSharedKeyAccess,allowBlobPublicAccess:allowBlobPublicAccess,enableHttpsTrafficOnly:enableHttpsTrafficOnly,minimumTlsVersion:minimumTlsVersion,publicNetworkAccess:publicNetworkAccess,sku:sku.name,kind:kind,provisioningState:provisioningState}"
    )
    Assert-AuditCondition (
        $storage.allowSharedKeyAccess -eq $false
    ) "storage_shared_key_enabled"
    Assert-AuditCondition (
        $storage.allowBlobPublicAccess -eq $false
    ) "storage_public_blob_enabled"
    Assert-AuditCondition (
        $storage.enableHttpsTrafficOnly -eq $true
    ) "storage_https_disabled"
    Assert-AuditCondition (
        $storage.minimumTlsVersion -eq "TLS1_2"
    ) "storage_tls_drift"
    Assert-AuditCondition (
        $storage.publicNetworkAccess -eq "Enabled"
    ) "storage_network_drift"
    Assert-AuditCondition (
        $storage.sku -eq "Standard_LRS" -and
        $storage.kind -eq "StorageV2" -and
        $storage.provisioningState -eq "Succeeded"
    ) "storage_profile_drift"

    $tableScope = "$($storage.id)/tableServices/default/tables/commands"
    $queueScope = "$($storage.id)/queueServices/default/queues/commands"
    $storageRoles = @(
        Invoke-AzJson -Arguments @(
            "role", "assignment", "list",
            "--scope", ([string]$storage.id),
            "--query",
            "[].{principalId:principalId,roleDefinitionName:roleDefinitionName,scope:scope}"
        )
    )
    $tableRoles = @(
        Invoke-AzJson -Arguments @(
            "role", "assignment", "list",
            "--scope", $tableScope,
            "--query",
            "[].{principalId:principalId,roleDefinitionName:roleDefinitionName,scope:scope}"
        )
    )
    $queueRoles = @(
        Invoke-AzJson -Arguments @(
            "role", "assignment", "list",
            "--scope", $queueScope,
            "--query",
            "[].{principalId:principalId,roleDefinitionName:roleDefinitionName,scope:scope}"
        )
    )
    Assert-AuditCondition (
        Test-ExactRole -Assignments $tableRoles -PrincipalId ([string]$app.principalId) -RoleName "Storage Table Data Contributor" -Scope $tableScope
    ) "table_role_missing"
    Assert-AuditCondition (
        Test-ExactRole -Assignments $queueRoles -PrincipalId ([string]$app.principalId) -RoleName "Storage Queue Data Contributor" -Scope $queueScope
    ) "queue_writer_role_missing"
    Assert-AuditCondition (
        Test-ExactRole -Assignments $queueRoles -PrincipalId ([string]$auth.owner) -RoleName "Storage Queue Data Message Processor" -Scope $queueScope
    ) "queue_owner_role_missing"

    $currentStage = "github_federation"
    $deploymentApps = @(
        Invoke-AzJson -Arguments @(
            "ad", "app", "list",
            "--display-name", $deploymentAppName,
            "--query", "[].{id:id,appId:appId}"
        )
    )
    Assert-AuditCondition (
        $deploymentApps.Count -eq 1
    ) "deployment_app_ambiguous"
    if ($deploymentApps.Count -eq 1) {
        $credentials = @(
            Invoke-AzJson -Arguments @(
                "ad", "app", "federated-credential", "list",
                "--id", ([string]$deploymentApps[0].id),
                "--query", "[].{name:name,issuer:issuer,subject:subject,audiences:audiences}"
            )
        )
        foreach ($branch in @("main", "develop")) {
            $credential = @(
                $credentials | Where-Object {
                    $_.name -eq "github-$branch"
                }
            )
            $subjectPattern = (
                "^repo:[^:]+/" + $expectedRepository +
                "(?:@[^:]+)?:ref:refs/heads/" + $branch + "$"
            )
            Assert-AuditCondition (
                $credential.Count -eq 1 -and
                $credential[0].issuer -eq
                    "https://token.actions.githubusercontent.com" -and
                @($credential[0].audiences).Count -eq 1 -and
                $credential[0].audiences[0] -eq
                    "api://AzureADTokenExchange" -and
                ([string]$credential[0].subject) -match $subjectPattern
            ) ("github_" + $branch + "_federation_drift")
        }

        $deploymentSp = Invoke-AzJson -Arguments @(
            "ad", "sp", "show",
            "--id", ([string]$deploymentApps[0].appId),
            "--query", "{id:id}"
        )
        $deploymentRoles = @(
            Invoke-AzJson -Arguments @(
                "role", "assignment", "list",
                "--assignee", ([string]$deploymentSp.id),
                "--all",
                "--query",
                "[].{principalId:principalId,roleDefinitionName:roleDefinitionName,scope:scope}"
            )
        )
        Assert-AuditCondition (
            $deploymentRoles.Count -eq 1 -and
            (Test-ExactRole -Assignments $deploymentRoles -PrincipalId ([string]$deploymentSp.id) -RoleName "Container Apps Contributor" -Scope ([string]$app.id))
        ) "deployment_role_scope_drift"
        Assert-AuditCondition (
            @(
                $storageRoles | Where-Object {
                    ([string]$_.principalId).ToLowerInvariant() -eq
                        ([string]$deploymentSp.id).ToLowerInvariant()
                }
            ).Count -eq 0
        ) "deployment_identity_has_storage_access"
    }

    $currentStage = "budget"
    $budget = Invoke-AzJson -Arguments @(
        "consumption", "budget", "show",
        "--budget-name", $budgetName,
        "--query",
        "{amount:amount,timeGrain:timeGrain,notifications:notifications}"
    )
    $notifications = @(
        $budget.notifications.PSObject.Properties |
            ForEach-Object { $_.Value }
    )
    $thresholds = @(
        $notifications |
            ForEach-Object { [int]$_.threshold } |
            Sort-Object
    )
    $alertRecipients = @(
        $notifications |
            ForEach-Object { @($_.contactEmails) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
            ForEach-Object { ([string]$_).ToLowerInvariant() } |
            Sort-Object -Unique
    )
    Assert-AuditCondition (
        [double]$budget.amount -eq 4.6 -and
        $budget.timeGrain -eq "Monthly"
    ) "budget_profile_drift"
    Assert-AuditCondition (
        ($thresholds -join ",") -eq "50,80,100" -and
        @(
            $notifications | Where-Object {
                $_.enabled -ne $true -or
                $_.operator -ne "GreaterThan"
            }
        ).Count -eq 0
    ) "budget_alert_drift"
    Assert-AuditCondition (
        $alertRecipients.Count -eq 1
    ) "budget_recipient_drift"

    $currentStage = "cloud_health"
    $health = Invoke-RestMethod (
        "https://" + [string]$app.fqdn + "/health"
    ) -TimeoutSec 120
    Assert-AuditCondition (
        $health.status -eq "ok" -and
        $health.service -eq "jarvis-os-cloud-planner" -and
        $health.remote_access_verified -eq $true -and
        $health.remote_transport -eq "azure_queue" -and
        $health.build_sha -eq $deployedBuildSha
    ) "cloud_health_drift"
}
catch {
    Add-AuditFailure -Code ("audit_execution_failed_" + $currentStage)
}

$safeResult = @{
    checkedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    status = if ($failures.Count -eq 0) { "OK" } else { "FAILED" }
    subscription = $expectedSubscriptionName
    checks = if ($failures.Count -eq 0) {
        @(
            "identity_and_roles",
            "storage_security",
            "budget_guardrail",
            "github_federation",
            "cloud_health"
        )
    }
    else {
        @($failures)
    }
}
Write-SafeAuditResult -Result $safeResult
if ($failures.Count -gt 0) {
    exit 1
}
exit 0
