param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Mt5Path = (Join-Path $env:ProgramFiles "OANDA TMS MT5 Terminal\terminal64.exe"),
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "JARVIS OS Forex Observer"
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$terminalPath = [IO.Path]::GetFullPath($Mt5Path)
$watchdogPath = Join-Path $projectPath "tools\forex_observer_watchdog.ps1"

if ($Remove) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
    Write-Output "JARVIS OS Forex Observer autostart removed."
    exit 0
}

foreach ($requiredPath in @($terminalPath, $watchdogPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Forex observation component is missing."
    }
}

$userId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powershellPath = Join-Path $env:SystemRoot (
    "System32\WindowsPowerShell\v1.0\powershell.exe"
)
$arguments = (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    $watchdogPath + '" -Mt5Path "' + $terminalPath + '"'
)
$action = New-ScheduledTaskAction `
    -Execute $powershellPath `
    -Argument $arguments `
    -WorkingDirectory $projectPath
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$trigger.Delay = "PT40S"
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$definition = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description (
        "Starts OANDA TMS MT5 after sign-in and records read-only JARVIS OS " +
        "Forex observations every 15 minutes. It cannot execute orders."
    )

Register-ScheduledTask `
    -TaskName $taskName `
    -InputObject $definition `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "JARVIS OS Forex Observer autostart installed and started."
