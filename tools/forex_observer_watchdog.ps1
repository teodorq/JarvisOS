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
$runnerPath = Join-Path $projectPath "tools\run_forex_paper_cycle.py"
$readinessPath = Join-Path $projectPath "tools\check_mt5_market_ready.py"
$dataPath = Join-Path $projectPath "data\trading"
$logPath = Join-Path $dataPath "forex_paper_watchdog.log"
$outputPath = Join-Path $dataPath "forex_paper_last.json"
$errorPath = Join-Path $dataPath "forex_paper_last.error.log"
$statusPath = Join-Path $dataPath "forex_observer_status.json"

foreach ($requiredPath in @(
    $terminalPath,
    $pythonPath,
    $runnerPath,
    $readinessPath
)) {
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

function Write-ObserverStatus {
    param(
        [string]$Status,
        [bool]$MarketWindowOpen,
        [bool]$Mt5Running,
        [string]$Detail
    )
    $lastCycleObservedAt = ""
    try {
        if (Test-Path -LiteralPath $outputPath -PathType Leaf) {
            $lastResult = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8 |
                ConvertFrom-Json
            $lastCycleObservedAt = [string]$lastResult.observed_at
        }
    }
    catch {
        $lastCycleObservedAt = ""
    }
    $payload = [ordered]@{
        schema_version = 1
        status = $Status
        checked_at = [DateTime]::UtcNow.ToString("o")
        market_window_open = $MarketWindowOpen
        mt5_running = $Mt5Running
        last_cycle_observed_at = $lastCycleObservedAt
        interval_minutes = $IntervalMinutes
        detail = $Detail
        broker_orders_sent = $false
        live_orders_sent = $false
        real_money_access = $false
    }
    $temporaryStatusPath = Join-Path $dataPath (
        "forex_observer_status.$PID.tmp"
    )
    try {
        $payload | ConvertTo-Json -Depth 4 -Compress |
            Set-Content -LiteralPath $temporaryStatusPath -Encoding UTF8
        Move-Item -LiteralPath $temporaryStatusPath -Destination $statusPath -Force
    }
    finally {
        Remove-Item -LiteralPath $temporaryStatusPath -Force -ErrorAction SilentlyContinue
    }
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
    if ($null -eq $process) {
        Start-Process `
            -FilePath $terminalPath `
            -WorkingDirectory (Split-Path -Parent $terminalPath) | Out-Null
        Write-ObserverLog "MT5 start requested."
        $deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
        do {
            Start-Sleep -Seconds 3
            $process = Get-RunningMt5Process
        } while ($null -eq $process -and (Get-Date) -lt $deadline)
    }
    if ($null -eq $process) {
        return $null
    }
    $readinessDeadline = (Get-Date).AddSeconds($StartupWaitSeconds)
    do {
        $probe = Start-Process `
            -FilePath $pythonPath `
            -ArgumentList ('"' + $readinessPath + '"') `
            -WorkingDirectory $projectPath `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
        if ($probe.ExitCode -eq 0) {
            Write-ObserverLog "MT5 market data ready."
            return $process
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $readinessDeadline)
    Write-ObserverLog "MT5 market data readiness timed out."
    return $null
}

function Invoke-ForexPaperCycle {
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
        Write-ObserverLog "PAPER cycle produced no result; exit $($process.ExitCode)."
        return
    }
    try {
        $result = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $executionCount = 0
        $positionCount = ""
        $reason = ""
        if ($result.PSObject.Properties.Name -contains "reason") {
            $reason = $result.reason
        }
        if ($result.PSObject.Properties.Name -contains "paper") {
            $executionCount = @($result.paper.execution.executions).Count
            $positionCount = $result.paper.account.position_count
        }
        $historyStatus = $result.activity_history_status
        Write-ObserverLog (
            "PAPER cycle $($result.status); reason=$reason; " +
            "executions=$executionCount; positions=$positionCount; " +
            "broker_orders_sent=$($result.broker_orders_sent); " +
            "live_orders_sent=$($result.live_orders_sent); " +
            "activity_history=$historyStatus."
        )
    }
    catch {
        Write-ObserverLog "PAPER result could not be parsed; exit $($process.ExitCode)."
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
    Write-ObserverLog "Forex runtime started in AUTONOMOUS_LOCAL_PAPER mode."
    Write-ObserverStatus "STARTING" $false $false "Observer uruchomiony."
    while ($true) {
        try {
            if (-not (Test-ForexMarketWindow)) {
                Write-ObserverLog "Forex market is closed; data quota preserved."
                Write-ObserverStatus `
                    "MARKET_CLOSED_IDLE" `
                    $false `
                    $false `
                    "Rynek jest zamkniety; MT5 uruchomi sie w oknie handlowym."
            }
            else {
                $mt5 = Start-Mt5IfNeeded
                if ($null -eq $mt5) {
                    Write-ObserverLog "MT5 did not become available; no PAPER cycle run."
                    Write-ObserverStatus `
                        "MT5_UNAVAILABLE" `
                        $true `
                        $false `
                        "MT5 nie stal sie dostepny; cykl PAPER pominiety."
                }
                else {
                    Write-ObserverStatus `
                        "RUNNING_CYCLE" `
                        $true `
                        $true `
                        "Trwa lokalny cykl PAPER."
                    Invoke-ForexPaperCycle
                    Write-ObserverStatus `
                        "WAITING_NEXT_CYCLE" `
                        $true `
                        $true `
                        "Cykl zakonczony; oczekiwanie na nastepny interwal."
                }
            }
        }
        catch {
            Write-ObserverLog "Cycle failed safely; no broker order execution is available."
            Write-ObserverStatus `
                "CYCLE_FAILED_SAFE" `
                (Test-ForexMarketWindow) `
                ($null -ne (Get-RunningMt5Process)) `
                "Cykl zakonczyl sie bezpiecznie bez dostepu do zlecen brokera."
        }
        Start-Sleep -Seconds ($IntervalMinutes * 60)
    }
}
finally {
    Write-ObserverStatus "STOPPED" $false $false "Observer zostal zatrzymany."
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
