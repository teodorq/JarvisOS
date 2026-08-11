param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$pythonwPath = Join-Path $projectPath ".venv\Scripts\pythonw.exe"
$mainPath = Join-Path $projectPath "main.py"
$runtimePath = Join-Path $projectPath "runtime"
$logPath = Join-Path $runtimePath "jarvis_watchdog.log"
$stopPath = Join-Path $runtimePath "jarvis_watchdog.stop"

if (-not (Test-Path -LiteralPath $pythonwPath -PathType Leaf)) {
    throw "JARVIS OS Python runtime is missing."
}
if (-not (Test-Path -LiteralPath $mainPath -PathType Leaf)) {
    throw "JARVIS OS entry point is missing."
}

New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null

function Write-WatchdogLog {
    param([string]$Message)

    if ((Test-Path -LiteralPath $logPath) -and
        (Get-Item -LiteralPath $logPath).Length -gt 262144) {
        Move-Item -LiteralPath $logPath -Destination "$logPath.previous" -Force
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Value "$timestamp $Message" -Encoding UTF8
}

function Get-RunningJarvisProcess {
    $escapedMainPath = [regex]::Escape($mainPath)
    $record = Get-CimInstance Win32_Process |
        Where-Object {
            $_.ExecutablePath -eq $pythonwPath -and
            $_.CommandLine -match $escapedMainPath
        } |
        Sort-Object CreationDate |
        Select-Object -First 1
    if ($null -eq $record) {
        return $null
    }
    return Get-Process -Id $record.ProcessId -ErrorAction SilentlyContinue
}

$mutex = New-Object Threading.Mutex($false, "Local\JARVIS_OS_WATCHDOG")
$ownsMutex = $false

try {
    try {
        $ownsMutex = $mutex.WaitOne(0, $false)
    }
    catch [Threading.AbandonedMutexException] {
        $ownsMutex = $true
    }
    if (-not $ownsMutex) {
        exit 0
    }

    $restartDelaySeconds = 5
    while ($true) {
        if (Test-Path -LiteralPath $stopPath) {
            Remove-Item -LiteralPath $stopPath -Force
            Write-WatchdogLog "Stop marker received; watchdog is exiting."
            break
        }

        $startedAt = Get-Date
        $exitCode = -1
        try {
            $process = Get-RunningJarvisProcess
            if ($null -eq $process) {
                $argument = '"' + $mainPath + '"'
                $process = Start-Process `
                    -FilePath $pythonwPath `
                    -ArgumentList $argument `
                    -WorkingDirectory $projectPath `
                    -PassThru
                Write-WatchdogLog "JARVIS OS started with PID $($process.Id)."
            }
            else {
                Write-WatchdogLog "Existing JARVIS OS PID $($process.Id) adopted."
            }
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        }
        catch {
            Write-WatchdogLog "Start or wait failed: $($_.Exception.Message)"
        }

        $runtimeSeconds = ((Get-Date) - $startedAt).TotalSeconds
        Write-WatchdogLog (
            "JARVIS OS exited with code $exitCode after " +
            "$([Math]::Round($runtimeSeconds)) seconds; restart in " +
            "$restartDelaySeconds seconds."
        )
        Start-Sleep -Seconds $restartDelaySeconds

        if ($runtimeSeconds -ge 300) {
            $restartDelaySeconds = 5
        }
        else {
            $restartDelaySeconds = [Math]::Min(60, $restartDelaySeconds * 2)
        }
    }
}
finally {
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
