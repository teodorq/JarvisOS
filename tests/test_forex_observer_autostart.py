from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (
    ROOT / "tools" / "install_forex_observer_autostart.ps1"
).read_text(encoding="utf-8")
WATCHDOG = (
    ROOT / "tools" / "forex_observer_watchdog.ps1"
).read_text(encoding="utf-8")


def test_installer_uses_hidden_limited_interactive_logon_task() -> None:
    assert '$taskName = "JARVIS OS Forex Observer"' in INSTALLER
    assert "New-ScheduledTaskTrigger -AtLogOn" in INSTALLER
    assert "-WindowStyle Hidden" in INSTALLER
    assert "-LogonType Interactive" in INSTALLER
    assert "-RunLevel Limited" in INSTALLER
    assert "-MultipleInstances IgnoreNew" in INSTALLER
    assert "Start-ScheduledTask -TaskName $taskName" in INSTALLER
    assert "-RepetitionInterval (New-TimeSpan -Minutes 15)" in INSTALLER
    assert "-RepetitionDuration (New-TimeSpan -Days 3650)" in INSTALLER
    assert "-Trigger @($trigger, $recoveryTrigger)" in INSTALLER
    assert "-MultipleInstances IgnoreNew" in INSTALLER


def test_installer_has_reversible_remove_path() -> None:
    assert "[switch]$Remove" in INSTALLER
    assert "Stop-ScheduledTask -TaskName $taskName" in INSTALLER
    assert "Unregister-ScheduledTask" in INSTALLER


def test_installer_stops_running_instance_before_registering_update() -> None:
    update_stop = INSTALLER.index("$existingTask = Get-ScheduledTask")
    registration = INSTALLER.index("Register-ScheduledTask")
    assert update_stop < registration
    update_section = INSTALLER[update_stop:registration]
    assert "Stop-ScheduledTask -TaskName $taskName" in update_section
    assert "$stopDeadline = (Get-Date).AddSeconds(10)" in update_section
    assert "Existing Forex observer did not stop before update." in update_section


def test_watchdog_has_bounded_interval_and_single_instance() -> None:
    assert "[ValidateRange(5, 60)]" in WATCHDOG
    assert "[int]$IntervalMinutes = 15" in WATCHDOG
    assert "Local\\JARVIS_OS_FOREX_OBSERVER" in WATCHDOG
    assert "[ValidateRange(30, 300)]" in WATCHDOG
    assert "[int]$ProtectionIntervalSeconds = 60" in WATCHDOG
    assert "Start-Sleep -Seconds $sleepSeconds" in WATCHDOG
    assert "Invoke-ForexPaperProtection" in WATCHDOG
    assert "protection_consecutive_failure_count" in WATCHDOG
    assert "protection_attention_required" in WATCHDOG
    assert "PROTECTION_ATTENTION_REQUIRED" in WATCHDOG
    assert "Update-ProtectionHealth" in WATCHDOG
    assert '$Result.PSObject.Properties.Name -contains "reason"' in WATCHDOG
    assert '"protection_consecutive_failure_count"' in WATCHDOG
    assert "$persistentFailures" in WATCHDOG
    assert "position_check_required_before_full_cycle" in WATCHDOG
    assert "new_entries_unlocked_after_position_check" in WATCHDOG
    assert "protection_gap_seconds_before_last_check" in WATCHDOG
    assert "previous_protection_check_restored" in WATCHDOG
    assert "last_recovery_gap_seconds" in WATCHDOG
    assert "last_recovery_gap_detected_at" in WATCHDOG
    assert "Restore-PreviousProtectionState" in WATCHDOG
    assert "Runtime gap detected before position check" in WATCHDOG
    assert "Test-ProtectionResultHealthy" in WATCHDOG
    assert "Invoke-PositionSafetyCheck" in WATCHDOG
    assert '"POSITION_CHECK_REQUIRED"' in WATCHDOG
    assert "Test-ForexMarketWindow" in WATCHDOG
    assert "Forex market is closed; data quota preserved." in WATCHDOG
    assert "[DayOfWeek]::Sunday" in WATCHDOG
    assert "$utcNow.Hour -ge 22" in WATCHDOG
    assert "forex_observer_status.json" in WATCHDOG
    assert "Write-ObserverStatus" in WATCHDOG
    assert '"MARKET_CLOSED_IDLE"' in WATCHDOG
    assert "broker_orders_sent = $false" in WATCHDOG
    assert "live_orders_sent = $false" in WATCHDOG
    assert "real_money_access = $false" in WATCHDOG


def test_watchdog_calls_only_the_local_paper_entry_point() -> None:
    assert '"tools\\run_forex_paper_cycle.py"' in WATCHDOG
    assert '"tools\\run_forex_paper_protection.py"' in WATCHDOG
    assert "forex_paper_last.json" in WATCHDOG
    assert "ForexPaperExecutionEngine" not in WATCHDOG
    assert "apply_plan" not in WATCHDOG
    assert "submit_live_order" not in WATCHDOG
    assert "order_send" not in WATCHDOG
    assert "activity_history" in WATCHDOG
    assert "PAPER protection" in WATCHDOG
    preflight = WATCHDOG.index(
        "$positionCheckPassed = Invoke-PositionSafetyCheck"
    )
    full_cycle = WATCHDOG.index("Invoke-ForexPaperCycle", preflight)
    assert preflight < full_cycle
    assert "Full PAPER cycle skipped until position check passes." in WATCHDOG
    assert (
        "Restore-PreviousProtectionState\n"
        '    Write-ObserverLog "Forex runtime started'
    ) in WATCHDOG


def test_watchdog_starts_only_the_configured_mt5_binary() -> None:
    assert "[IO.Path]::GetFullPath($Mt5Path)" in WATCHDOG
    assert "-FilePath $terminalPath" in WATCHDOG
    assert "Get-CimInstance Win32_Process" in WATCHDOG
    assert "AUTONOMOUS_LOCAL_PAPER" in WATCHDOG
    assert "no broker order execution is available" in WATCHDOG
    assert '"tools\\check_mt5_market_ready.py"' in WATCHDOG
    assert "MT5 market data ready." in WATCHDOG
    assert "MT5 market data readiness timed out." in WATCHDOG
