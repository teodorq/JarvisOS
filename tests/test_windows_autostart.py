from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_autostart_runs_only_at_sign_in() -> None:
    installer = (ROOT / "tools" / "install_jarvis_autostart.ps1").read_text(
        encoding="utf-8"
    )

    assert "New-ScheduledTaskTrigger -AtLogOn" in installer
    assert "RepetitionInterval" not in installer
    assert "-Trigger $trigger" in installer


def test_reinstall_clears_the_previous_stop_marker() -> None:
    installer = (ROOT / "tools" / "install_jarvis_autostart.ps1").read_text(
        encoding="utf-8"
    )

    clear_marker = (
        "Remove-Item -LiteralPath $stopPath -Force "
        "-ErrorAction SilentlyContinue"
    )
    assert clear_marker in installer
    assert installer.index(clear_marker) < installer.index(
        "Register-ScheduledTask"
    )


def test_watchdog_does_not_restart_after_a_normal_exit() -> None:
    watchdog = (ROOT / "tools" / "jarvis_watchdog.ps1").read_text(
        encoding="utf-8"
    )

    clean_exit = "if ($exitCode -eq 0)"
    assert clean_exit in watchdog
    assert watchdog.index(clean_exit) < watchdog.index(
        "Start-Sleep -Seconds $restartDelaySeconds"
    )
    assert "watchdog is exiting." in watchdog
