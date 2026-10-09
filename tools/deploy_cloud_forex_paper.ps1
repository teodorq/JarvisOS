[CmdletBinding()]
param(
    [string]$ContainerImage = "",
    [string]$BuildSha = "",
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $ProjectRoot "config\forex.env"
$ResourceGroup = "rg-jarvis-os-cloud"
$PlannerName = "jarvis-os-planner"
$JobName = "jarvis-os-forex-paper"

function Get-PrivateSetting([string]$Name) {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Brakuje lokalnego pliku config/forex.env."
    }
    foreach ($Line in Get-Content -LiteralPath $ConfigPath -Encoding UTF8) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        if ($Key.Trim() -ne $Name) {
            continue
        }
        $Selected = $Value.Trim()
        if (
            $Selected.Length -ge 2 -and
            (($Selected.StartsWith('"') -and $Selected.EndsWith('"')) -or
             ($Selected.StartsWith("'") -and $Selected.EndsWith("'")))
        ) {
            $Selected = $Selected.Substring(1, $Selected.Length - 2)
        }
        if (-not $Selected -or $Selected.Length -gt 4096 -or $Selected.Contains("`n")) {
            throw "Nieprawidłowa wartość $Name."
        }
        return $Selected
    }
    throw "Brakuje $Name w config/forex.env."
}

function Invoke-Azure([string[]]$Arguments) {
    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Polecenie Azure nie powiodło się. Zaloguj ponownie przez: az login"
    }
}

$TwelveDataKey = Get-PrivateSetting "JARVIS_OS_TWELVE_DATA_API_KEY"
$FmpKey = Get-PrivateSetting "JARVIS_OS_FMP_API_KEY"

try {
    Invoke-Azure @(
        "group", "show",
        "--name", $ResourceGroup,
        "--query", "properties.provisioningState",
        "--output", "none",
        "--only-show-errors"
    )

    if (-not $ContainerImage) {
        $ContainerImage = (& az containerapp show `
            --name $PlannerName `
            --resource-group $ResourceGroup `
            --query "properties.template.containers[0].image" `
            --output tsv `
            --only-show-errors).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Nie udało się odczytać obrazu JARVIS OS."
        }
    }
    if (-not $BuildSha) {
        $BuildSha = (& az containerapp show `
            --name $PlannerName `
            --resource-group $ResourceGroup `
            --query "properties.template.containers[0].env[?name=='JARVIS_OS_BUILD_SHA'].value | [0]" `
            --output tsv `
            --only-show-errors).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Nie udało się odczytać wersji JARVIS OS."
        }
    }
    if ($BuildSha -notmatch '^[a-f0-9]{40}$') {
        throw "Wdrożenie wymaga pełnego, niezmiennego SHA Git."
    }
    if ($ContainerImage -notmatch (':sha-' + [regex]::Escape($BuildSha) + '$')) {
        throw "Obraz chmurowy nie odpowiada podanemu SHA Git."
    }
    $StorageAccount = (& az containerapp show `
        --name $PlannerName `
        --resource-group $ResourceGroup `
        --query "properties.template.containers[0].env[?name=='JARVIS_OS_REMOTE_STORAGE_ACCOUNT'].value | [0]" `
        --output tsv `
        --only-show-errors).Trim()
    if ($LASTEXITCODE -ne 0 -or $StorageAccount -notmatch '^[a-z0-9]{3,24}$') {
        throw "Nie udało się bezpiecznie odczytać konta Storage JARVIS OS."
    }

    Invoke-Azure @(
        "deployment", "group", "create",
        "--name", "jarvis-os-forex-paper",
        "--resource-group", $ResourceGroup,
        "--template-file", (Join-Path $ProjectRoot "infra\azure\paper-job.bicep"),
        "--parameters",
        "namePrefix=jarvis-os",
        "containerImage=$ContainerImage",
        "buildSha=$BuildSha",
        "storageAccountName=$StorageAccount",
        "managedEnvironmentName=jarvis-os-env",
        "twelveDataApiKey=$TwelveDataKey",
        "fmpApiKey=$FmpKey",
        "--only-show-errors",
        "--output", "none"
    )

    $Verified = (& az containerapp job show `
        --name $JobName `
        --resource-group $ResourceGroup `
        --query "{state:properties.provisioningState,trigger:properties.configuration.triggerType,cron:properties.configuration.scheduleTriggerConfig.cronExpression,identity:identity.type,image:properties.template.containers[0].image}" `
        --output json `
        --only-show-errors) | ConvertFrom-Json
    if (
        $LASTEXITCODE -ne 0 -or
        $Verified.state -ne "Succeeded" -or
        $Verified.trigger -ne "Schedule" -or
        $Verified.cron -ne "2,17,32,47 * * * *" -or
        $Verified.identity -ne "SystemAssigned" -or
        $Verified.image -ne $ContainerImage
    ) {
        throw "Zadanie PAPER nie przeszło kontroli konfiguracji."
    }

    if ($StartNow) {
        Invoke-Azure @(
            "containerapp", "job", "start",
            "--name", $JobName,
            "--resource-group", $ResourceGroup,
            "--only-show-errors",
            "--output", "none"
        )
    }
    Write-Output "JARVIS OS Forex PAPER: wdrożenie Azure gotowe."
} finally {
    $TwelveDataKey = $null
    $FmpKey = $null
}
