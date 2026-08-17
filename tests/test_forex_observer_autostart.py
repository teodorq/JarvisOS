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


def test_installer_has_reversible_remove_path() -> None:
    assert "[switch]$Remove" in INSTALLER
    assert "Stop-ScheduledTask -TaskName $taskName" in INSTALLER
    assert "Unregister-ScheduledTask" in INSTALLER


def test_watchdog_has_bounded_interval_and_single_instance() -> None:
    assert "[ValidateRange(5, 60)]" in WATCHDOG
    assert "[int]$IntervalMinutes = 15" in WATCHDOG
    assert "Local\\JARVIS_OS_FOREX_OBSERVER" in WATCHDOG
    assert "Start-Sleep -Seconds ($IntervalMinutes * 60)" in WATCHDOG
    assert "Test-ForexMarketWindow" in WATCHDOG
    assert "Forex market is closed; data quota preserved." in WATCHDOG
    assert "[DayOfWeek]::Sunday" in WATCHDOG
    assert "$utcNow.Hour -ge 22" in WATCHDOG


def test_watchdog_calls_only_the_observation_entry_point() -> None:
    assert '"tools\\run_forex_observation.py"' in WATCHDOG
    assert "forex_observer_last.json" in WATCHDOG
    assert "ForexPaperExecutionEngine" not in WATCHDOG
    assert "apply_plan" not in WATCHDOG
    assert "submit_live_order" not in WATCHDOG
    assert "order_send" not in WATCHDOG


def test_watchdog_starts_only_the_configured_mt5_binary() -> None:
    assert "[IO.Path]::GetFullPath($Mt5Path)" in WATCHDOG
    assert "-FilePath $terminalPath" in WATCHDOG
    assert "Get-CimInstance Win32_Process" in WATCHDOG
    assert "OBSERVATION_ONLY" in WATCHDOG
