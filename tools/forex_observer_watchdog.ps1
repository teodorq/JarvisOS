param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Mt5Path = (Join-Path $env:ProgramFiles "OANDA TMS MT5 Terminal\terminal64.exe"),
    [ValidateRange(5, 60)]
    [int]$IntervalMinutes = 15,
    [ValidateRange(15, 180)]
    [int]$StartupWaitSeconds = 90
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$terminalPath = [IO.Path]::GetFullPath($Mt5Path)
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
$runnerPath = Join-Path $projectPath "tools\run_forex_observation.py"
$dataPath = Join-Path $projectPath "data\trading"
$logPath = Join-Path $dataPath "forex_observer_watchdog.log"
$outputPath = Join-Path $dataPath "forex_observer_last.json"
$errorPath = Join-Path $dataPath "forex_observer_last.error.log"

foreach ($requiredPath in @($terminalPath, $pythonPath, $runnerPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Forex observation component is missing."
    }
}

New-Item -ItemType Directory -Path $dataPath -Force | Out-Null

function Write-ObserverLog {
    param([string]$Message)

    if ((Test-Path -LiteralPath $logPath) -and
        (Get-Item -LiteralPath $logPath).Length -gt 524288) {
        Move-Item -LiteralPath $logPath -Destination "$logPath.previous" -Force
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Value "$timestamp $Message" -Encoding UTF8
}

function Get-RunningMt5Process {
    $record = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -eq $terminalPath } |
        Sort-Object CreationDate |
        Select-Object -First 1
    if ($null -eq $record) {
        return $null
    }
    return Get-Process -Id $record.ProcessId -ErrorAction SilentlyContinue
}

function Test-ForexMarketWindow {
    $utcNow = (Get-Date).ToUniversalTime()
    if ($utcNow.DayOfWeek -in @(
        [DayOfWeek]::Monday,
        [DayOfWeek]::Tuesday,
        [DayOfWeek]::Wednesday,
        [DayOfWeek]::Thursday
    )) {
        return $true
    }
    if ($utcNow.DayOfWeek -eq [DayOfWeek]::Friday) {
        return $utcNow.Hour -lt 21
    }
    if ($utcNow.DayOfWeek -eq [DayOfWeek]::Sunday) {
        return $utcNow.Hour -ge 22
    }
    return $false
}

function Start-Mt5IfNeeded {
    $process = Get-RunningMt5Process
    if ($null -ne $process) {
        return $process
    }
    Start-Process `
        -FilePath $terminalPath `
        -WorkingDirectory (Split-Path -Parent $terminalPath) | Out-Null
    Write-ObserverLog "MT5 start requested."
    $deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
    do {
        Start-Sleep -Seconds 3
        $process = Get-RunningMt5Process
    } while ($null -eq $process -and (Get-Date) -lt $deadline)
    if ($null -ne $process) {
        Start-Sleep -Seconds 15
    }
    return $process
}

function Invoke-ForexObservation {
    Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $errorPath -Force -ErrorAction SilentlyContinue
    $runnerArgument = '"' + $runnerPath + '"'
    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList $runnerArgument `
        -WorkingDirectory $projectPath `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outputPath `
        -RedirectStandardError $errorPath `
        -Wait `
        -PassThru
    if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        Write-ObserverLog "Observation produced no result; exit $($process.ExitCode)."
        return
    }
    try {
        $result = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $blocks = @($result.opening_blocks) -join ","
        Write-ObserverLog (
            "Observation $($result.status); blocks=$blocks; " +
            "proposed=$($result.proposed_instruction_count); " +
            "positions_unchanged=$($result.positions_unchanged); " +
            "paper_orders_sent=$($result.paper_orders_sent); " +
            "live_orders_sent=$($result.live_orders_sent)."
        )
    }
    catch {
        Write-ObserverLog "Observation result could not be parsed; exit $($process.ExitCode)."
    }
}

$mutex = New-Object Threading.Mutex($false, "Local\JARVIS_OS_FOREX_OBSERVER")
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
    Write-ObserverLog "Forex observer started in OBSERVATION_ONLY mode."
    while ($true) {
        try {
            if (-not (Test-ForexMarketWindow)) {
                Write-ObserverLog "Forex market is closed; data quota preserved."
            }
            else {
                $mt5 = Start-Mt5IfNeeded
                if ($null -eq $mt5) {
                    Write-ObserverLog "MT5 did not become available; no observation run."
                }
                else {
                    Invoke-ForexObservation
                }
            }
        }
        catch {
            Write-ObserverLog "Cycle failed safely; no order execution is available."
        }
        Start-Sleep -Seconds ($IntervalMinutes * 60)
    }
}
finally {
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
