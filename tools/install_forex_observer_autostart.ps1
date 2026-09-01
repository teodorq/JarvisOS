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

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existingTask -and $existingTask.State -eq "Running") {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $stopDeadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 200
        $existingTask = Get-ScheduledTask `
            -TaskName $taskName `
            -ErrorAction SilentlyContinue
    } while (
        $null -ne $existingTask -and
        $existingTask.State -eq "Running" -and
        (Get-Date) -lt $stopDeadline
    )
    if ($null -ne $existingTask -and $existingTask.State -eq "Running") {
        throw "Existing Forex observer did not stop before update."
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
$recoveryTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
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
    -Trigger @($trigger, $recoveryTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Description (
        "Starts OANDA TMS MT5 after sign-in and runs autonomous local JARVIS OS " +
        "Forex PAPER cycles every 15 minutes. A recovery trigger restarts the " +
        "observer if it exits. Existing PAPER positions receive a local MT5 " +
        "SL/TP check every minute. It cannot send broker orders."
    )

Register-ScheduledTask `
    -TaskName $taskName `
    -InputObject $definition `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "JARVIS OS Forex local PAPER autostart installed and started."
