param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "JARVIS OS Autostart"
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$watchdogPath = Join-Path $projectPath "tools\jarvis_watchdog.ps1"
$runtimePath = Join-Path $projectPath "runtime"
$stopPath = Join-Path $runtimePath "jarvis_watchdog.stop"

if ($Remove) {
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    New-Item -ItemType File -Path $stopPath -Force | Out-Null
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "JARVIS OS autostart removed."
    exit 0
}

if (-not (Test-Path -LiteralPath $watchdogPath -PathType Leaf)) {
    throw "JARVIS OS watchdog script is missing."
}

Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue

$userId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powershellPath = Join-Path $env:SystemRoot (
    "System32\WindowsPowerShell\v1.0\powershell.exe"
)
$arguments = (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    $watchdogPath + '"'
)
$action = New-ScheduledTaskAction `
    -Execute $powershellPath `
    -Argument $arguments `
    -WorkingDirectory $projectPath
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$trigger.Delay = "PT20S"
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
        "Keeps JARVIS OS available after sign-in and restarts it " +
        "after an unexpected exit."
    )

Register-ScheduledTask `
    -TaskName $taskName `
    -InputObject $definition `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "JARVIS OS autostart installed and started."
