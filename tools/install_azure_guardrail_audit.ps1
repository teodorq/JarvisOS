param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "JARVIS OS Azure Guardrail Audit"
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$auditPath = Join-Path $projectPath "tools\audit_azure_guardrails.ps1"

if ($Remove) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "JARVIS OS Azure guardrail audit removed."
    exit 0
}

if (-not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
    throw "JARVIS OS Azure guardrail audit script is missing."
}

$userId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powershellPath = Join-Path $env:SystemRoot (
    "System32\WindowsPowerShell\v1.0\powershell.exe"
)
$arguments = (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    $auditPath + '" -ProjectRoot "' + $projectPath + '"'
)
$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $arguments -WorkingDirectory $projectPath
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:00"
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
$definition = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description (
    "Checks JARVIS OS Azure security, cost and identity guardrails " +
    "locally without exporting live configuration."
)

Register-ScheduledTask -TaskName $taskName -InputObject $definition -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "JARVIS OS Azure guardrail audit installed and started."
