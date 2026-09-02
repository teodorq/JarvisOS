param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Mt5Path = (Join-Path $env:ProgramFiles "OANDA TMS MT5 Terminal\terminal64.exe"),
    [ValidateRange(5, 60)]
    [int]$IntervalMinutes = 15,
    [ValidateRange(15, 180)]
    [int]$StartupWaitSeconds = 90,
    [ValidateRange(30, 300)]
    [int]$ProtectionIntervalSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$terminalPath = [IO.Path]::GetFullPath($Mt5Path)
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
$runnerPath = Join-Path $projectPath "tools\run_forex_paper_cycle.py"
$protectionRunnerPath = Join-Path $projectPath (
    "tools\run_forex_paper_protection.py"
)
$readinessPath = Join-Path $projectPath "tools\check_mt5_market_ready.py"
$dataPath = Join-Path $projectPath "data\trading"
$logPath = Join-Path $dataPath "forex_paper_watchdog.log"
$outputPath = Join-Path $dataPath "forex_paper_last.json"
$errorPath = Join-Path $dataPath "forex_paper_last.error.log"
$statusPath = Join-Path $dataPath "forex_observer_status.json"
$protectionOutputPath = Join-Path $dataPath "forex_paper_protection_last.json"
$protectionErrorPath = Join-Path $dataPath "forex_paper_protection_last.error.log"
$script:lastProtectionStatus = "NOT_RUN"
$script:lastProtectionCheckedAt = ""
$script:lastProtectionReason = ""
$script:consecutiveProtectionFailures = 0
$script:positionCheckSatisfied = $false
$script:lastProtectionAttemptUtc = $null
$script:lastProtectionGapSeconds = 0
$script:previousProtectionCheckRestored = $false
$script:lastRecoveryGapSeconds = 0
$script:lastRecoveryGapDetectedAt = ""
$script:lastRecoveryReplayStatus = ""
$script:lastRecoveryReplayAt = ""
$script:lastRecoveryReplayExitCount = 0
$script:lastRecoveryReplayAmbiguousCount = 0

foreach ($requiredPath in @(
    $terminalPath,
    $pythonPath,
    $runnerPath,
    $protectionRunnerPath,
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
        protection_interval_seconds = $ProtectionIntervalSeconds
        protection_status = $script:lastProtectionStatus
        protection_checked_at = $script:lastProtectionCheckedAt
        last_successful_protection_at = if (
            $null -eq $script:lastProtectionAttemptUtc
        ) {
            ""
        }
        else {
            $script:lastProtectionAttemptUtc.ToString("o")
        }
        protection_reason = $script:lastProtectionReason
        protection_consecutive_failure_count = (
            $script:consecutiveProtectionFailures
        )
        protection_attention_required = (
            $script:consecutiveProtectionFailures -ge 3
        )
        protection_gap_seconds_before_last_check = (
            $script:lastProtectionGapSeconds
        )
        previous_protection_check_restored = (
            $script:previousProtectionCheckRestored
        )
        last_recovery_gap_seconds = $script:lastRecoveryGapSeconds
        last_recovery_gap_detected_at = $script:lastRecoveryGapDetectedAt
        last_recovery_replay_status = $script:lastRecoveryReplayStatus
        last_recovery_replay_at = $script:lastRecoveryReplayAt
        last_recovery_replay_exit_count = (
            $script:lastRecoveryReplayExitCount
        )
        last_recovery_replay_ambiguous_count = (
            $script:lastRecoveryReplayAmbiguousCount
        )
        position_check_required_before_full_cycle = (
            -not $script:positionCheckSatisfied
        )
        new_entries_unlocked_after_position_check = (
            $script:positionCheckSatisfied
        )
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

function Restore-PreviousProtectionState {
    if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) {
        return
    }
    try {
        if ((Get-Item -LiteralPath $statusPath).Length -gt 65536) {
            return
        }
        $previous = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $properties = @($previous.PSObject.Properties.Name)
        $timestampProperty = if (
            $properties -contains "last_successful_protection_at"
        ) {
            "last_successful_protection_at"
        }
        elseif (
            $properties -contains "protection_checked_at" -and
            [string]$previous.protection_status -in @(
                "NO_OPEN_POSITIONS",
                "NO_PROTECTION_TRIGGER",
                "PAPER_PROTECTION_APPLIED"
            )
        ) {
            "protection_checked_at"
        }
        else {
            ""
        }
        if ([string]::IsNullOrWhiteSpace($timestampProperty)) {
            return
        }
        $rawCheckedAt = [string]$previous.$timestampProperty
        if ([string]::IsNullOrWhiteSpace($rawCheckedAt)) {
            return
        }
        $parsed = [DateTimeOffset]::Parse(
            $rawCheckedAt,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        ).UtcDateTime
        if ($parsed -gt [DateTime]::UtcNow.AddMinutes(5)) {
            return
        }
        $script:lastProtectionAttemptUtc = $parsed
        $script:previousProtectionCheckRestored = $true
        if ($properties -contains "last_recovery_gap_seconds") {
            $previousGap = [long]$previous.last_recovery_gap_seconds
            $script:lastRecoveryGapSeconds = [Math]::Max(
                0,
                [Math]::Min(604800, $previousGap)
            )
        }
        if ($properties -contains "last_recovery_gap_detected_at") {
            $previousDetectedAt = (
                [string]$previous.last_recovery_gap_detected_at
            )
            $script:lastRecoveryGapDetectedAt = $previousDetectedAt.Substring(
                0,
                [Math]::Min(80, $previousDetectedAt.Length)
            )
        }
        if ($properties -contains "last_recovery_replay_status" -and
            [string]$previous.last_recovery_replay_status -eq (
                "RECOVERY_REPLAY_APPLIED"
            )) {
            $script:lastRecoveryReplayStatus = "RECOVERY_REPLAY_APPLIED"
            $script:lastRecoveryReplayAt = (
                [string]$previous.last_recovery_replay_at
            )
            $script:lastRecoveryReplayExitCount = [Math]::Max(
                0,
                [Math]::Min(
                    2,
                    [int]$previous.last_recovery_replay_exit_count
                )
            )
            $script:lastRecoveryReplayAmbiguousCount = [Math]::Max(
                0,
                [Math]::Min(
                    $script:lastRecoveryReplayExitCount,
                    [int]$previous.last_recovery_replay_ambiguous_count
                )
            )
        }
    }
    catch {
        $script:lastProtectionAttemptUtc = $null
        $script:previousProtectionCheckRestored = $false
        $script:lastRecoveryGapSeconds = 0
        $script:lastRecoveryGapDetectedAt = ""
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

function Invoke-ForexPaperProtection {
    param([object]$RecoverySinceUtc = $null)

    Remove-Item -LiteralPath $protectionOutputPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $protectionErrorPath -Force -ErrorAction SilentlyContinue
    $runnerArgument = '"' + $protectionRunnerPath + '"'
    if ($null -ne $RecoverySinceUtc) {
        $runnerArgument += (
            ' --recovery-since "' +
            ([DateTime]$RecoverySinceUtc).ToString("o") +
            '"'
        )
    }
    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList $runnerArgument `
        -WorkingDirectory $projectPath `
        -WindowStyle Hidden `
        -RedirectStandardOutput $protectionOutputPath `
        -RedirectStandardError $protectionErrorPath `
        -Wait `
        -PassThru
    if (-not (Test-Path -LiteralPath $protectionOutputPath -PathType Leaf)) {
        Write-ObserverLog (
            "PAPER protection produced no result; exit $($process.ExitCode)."
        )
        return $null
    }
    try {
        $result = Get-Content `
            -LiteralPath $protectionOutputPath `
            -Raw `
            -Encoding UTF8 | ConvertFrom-Json
        $executionCount = 0
        $positionCount = ""
        $replayStatus = "NOT_REPORTED"
        $replayExitCount = 0
        $replayAmbiguousCount = 0
        if ($result.PSObject.Properties.Name -contains "paper") {
            $executionCount = @($result.paper.execution.executions).Count
            $positionCount = $result.paper.account.position_count
        }
        if ($result.PSObject.Properties.Name -contains "recovery_replay") {
            $replay = $result.recovery_replay
            $replayStatus = [string]$replay.status
            if ($replay.PSObject.Properties.Name -contains (
                "historical_exit_count"
            )) {
                $replayExitCount = [Math]::Max(
                    0,
                    [Math]::Min(2, [int]$replay.historical_exit_count)
                )
            }
            if ($replay.PSObject.Properties.Name -contains (
                "ambiguous_bar_count"
            )) {
                $replayAmbiguousCount = [Math]::Max(
                    0,
                    [Math]::Min(
                        $replayExitCount,
                        [int]$replay.ambiguous_bar_count
                    )
                )
            }
            if ($replayStatus -eq "RECOVERY_REPLAY_APPLIED") {
                $script:lastRecoveryReplayStatus = $replayStatus
                $script:lastRecoveryReplayAt = [string]$result.observed_at
                $script:lastRecoveryReplayExitCount = $replayExitCount
                $script:lastRecoveryReplayAmbiguousCount = (
                    $replayAmbiguousCount
                )
            }
        }
        Write-ObserverLog (
            "PAPER protection $($result.status); " +
            "executions=$executionCount; positions=$positionCount; " +
            "replay=$replayStatus; replay_exits=$replayExitCount; " +
            "ambiguous=$replayAmbiguousCount; " +
            "broker_orders_sent=$($result.broker_orders_sent); " +
            "live_orders_sent=$($result.live_orders_sent)."
        )
        return $result
    }
    catch {
        Write-ObserverLog (
            "PAPER protection result could not be parsed; exit $($process.ExitCode)."
        )
        return $null
    }
}

function Update-ProtectionHealth {
    param([object]$Result)

    $script:lastProtectionCheckedAt = [DateTime]::UtcNow.ToString("o")
    if ($null -eq $Result) {
        $script:lastProtectionStatus = "PROTECTION_RESULT_UNAVAILABLE"
        $script:lastProtectionReason = "Brak prawidlowego wyniku ochrony."
        $script:consecutiveProtectionFailures += 1
        return
    }
    $status = [string]$Result.status
    $reason = ""
    if ($Result.PSObject.Properties.Name -contains "reason") {
        $reason = [string]$Result.reason
    }
    if ($reason.Length -gt 160) {
        $reason = $reason.Substring(0, 160)
    }
    $script:lastProtectionStatus = if ($status) {
        $status
    }
    else {
        "PROTECTION_STATUS_MISSING"
    }
    $script:lastProtectionReason = $reason
    if ($Result.PSObject.Properties.Name -contains (
        "protection_consecutive_failure_count"
    )) {
        try {
            $persistentFailures = [int](
                $Result.protection_consecutive_failure_count
            )
            $script:consecutiveProtectionFailures = [Math]::Max(
                0,
                [Math]::Min(1000, $persistentFailures)
            )
            return
        }
        catch {
            # Fall back to the in-process counter below.
        }
    }
    if ($script:lastProtectionStatus -in @(
        "NO_OPEN_POSITIONS",
        "NO_PROTECTION_TRIGGER",
        "PAPER_PROTECTION_APPLIED"
    )) {
        $script:consecutiveProtectionFailures = 0
    }
    else {
        $script:consecutiveProtectionFailures += 1
    }
}

function Write-ProtectionObserverStatus {
    if (-not $script:positionCheckSatisfied) {
        $blockedStatus = if ($script:consecutiveProtectionFailures -ge 3) {
            "PROTECTION_ATTENTION_REQUIRED"
        }
        else {
            "POSITION_CHECK_REQUIRED"
        }
        Write-ObserverStatus `
            $blockedStatus `
            $true `
            $true `
            "Kontrola pozycji nie przeszla; nowe wejscia PAPER sa wstrzymane."
        return
    }
    if ($script:consecutiveProtectionFailures -ge 3) {
        Write-ObserverStatus `
            "PROTECTION_ATTENTION_REQUIRED" `
            $true `
            $true `
            "Ochrona SL/TP wymaga uwagi; pelny cykl pozostaje aktywny."
        return
    }
    Write-ObserverStatus `
        "WAITING_NEXT_CYCLE" `
        $true `
        $true `
        "Ochrona SL/TP aktywna; oczekiwanie na pelny cykl."
}

function Test-ProtectionResultHealthy {
    param([object]$Result)

    if ($null -eq $Result -or
        -not ($Result.PSObject.Properties.Name -contains "status")) {
        return $false
    }
    return [string]$Result.status -in @(
        "NO_OPEN_POSITIONS",
        "NO_PROTECTION_TRIGGER",
        "PAPER_PROTECTION_APPLIED"
    )
}

function Invoke-PositionSafetyCheck {
    $attemptedAt = [DateTime]::UtcNow
    $recoverySinceUtc = $script:lastProtectionAttemptUtc
    if ($null -eq $script:lastProtectionAttemptUtc) {
        $script:lastProtectionGapSeconds = 0
    }
    else {
        $gap = [Math]::Floor(
            ($attemptedAt - $script:lastProtectionAttemptUtc).TotalSeconds
        )
        $script:lastProtectionGapSeconds = [Math]::Max(
            0,
            [Math]::Min(604800, [int]$gap)
        )
        if ($script:lastProtectionGapSeconds -gt (
            $ProtectionIntervalSeconds * 3
        )) {
            $script:lastRecoveryGapSeconds = (
                $script:lastProtectionGapSeconds
            )
            $script:lastRecoveryGapDetectedAt = $attemptedAt.ToString("o")
            Write-ObserverLog (
                "Runtime gap detected before position check; seconds=" +
                "$($script:lastProtectionGapSeconds)."
            )
        }
    }
    try {
        $result = Invoke-ForexPaperProtection `
            -RecoverySinceUtc $recoverySinceUtc
        Update-ProtectionHealth $result
        $passed = Test-ProtectionResultHealthy $result
        if ($passed) {
            $script:lastProtectionAttemptUtc = $attemptedAt
        }
    }
    catch {
        Update-ProtectionHealth $null
        $passed = $false
        Write-ObserverLog "Position safety check failed safely."
    }
    $script:positionCheckSatisfied = $passed
    Write-ObserverLog (
        "Position safety check $($script:lastProtectionStatus); " +
        "gap_seconds=$($script:lastProtectionGapSeconds); " +
        "full_cycle_unlocked=$passed."
    )
    return $passed
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
    Restore-PreviousProtectionState
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
                    if (-not $script:positionCheckSatisfied) {
                        Write-ObserverStatus `
                            "POSITION_CHECK_RUNNING" `
                            $true `
                            $true `
                            "Sprawdzam istniejaca pozycje przed pelnym cyklem."
                        $positionCheckPassed = Invoke-PositionSafetyCheck
                        if (-not $positionCheckPassed) {
                            Write-ObserverLog (
                                "Full PAPER cycle skipped until position check passes."
                            )
                            Write-ProtectionObserverStatus
                        }
                    }
                    if ($script:positionCheckSatisfied) {
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
        }
        catch {
            $script:positionCheckSatisfied = $false
            Write-ObserverLog "Cycle failed safely; no broker order execution is available."
            Write-ObserverStatus `
                "CYCLE_FAILED_SAFE" `
                (Test-ForexMarketWindow) `
                ($null -ne (Get-RunningMt5Process)) `
                "Cykl zakonczyl sie bezpiecznie bez dostepu do zlecen brokera."
        }
        if ((Test-ForexMarketWindow) -and
            -not $script:positionCheckSatisfied) {
            Start-Sleep -Seconds $ProtectionIntervalSeconds
            continue
        }
        $remainingSeconds = $IntervalMinutes * 60
        while ($remainingSeconds -gt 0) {
            $sleepSeconds = [Math]::Min(
                $ProtectionIntervalSeconds,
                $remainingSeconds
            )
            Start-Sleep -Seconds $sleepSeconds
            $remainingSeconds -= $sleepSeconds
            if (-not (Test-ForexMarketWindow)) {
                break
            }
            if ($null -ne (Get-RunningMt5Process)) {
                try {
                    $positionCheckPassed = Invoke-PositionSafetyCheck
                    Write-ProtectionObserverStatus
                    if (-not $positionCheckPassed) {
                        break
                    }
                }
                catch {
                    Write-ObserverLog (
                        "PAPER protection failed safely; full cycle remains scheduled."
                    )
                    Update-ProtectionHealth $null
                    $script:positionCheckSatisfied = $false
                    Write-ProtectionObserverStatus
                    break
                }
            }
            else {
                $script:positionCheckSatisfied = $false
                break
            }
        }
    }
}
finally {
    Write-ObserverStatus "STOPPED" $false $false "Observer zostal zatrzymany."
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
