from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_autostart_runs_only_at_sign_in() -> None:
    installer = (ROOT / "tools" / "install_jarvis_autostart.ps1").read_text(
        encoding="utf-8"
    )

    assert "New-ScheduledTaskTrigger -AtLogOn" in installer
    assert "RepetitionInterval" not in installer
    assert "-Trigger $trigger" in installer
    assert "-WindowStyle Hidden" in installer


def test_manual_launcher_and_shortcut_do_not_open_a_console() -> None:
    hidden = (ROOT / "start_jarvis.vbs").read_text(encoding="utf-8")
    scripts = (ROOT / "app/business/installation_scripts.py").read_text(
        encoding="utf-8"
    )
    assert "shell.Run command, 0, False" in hidden
    assert "start_jarvis.vbs" in scripts
    assert "$shortcut.TargetPath=$wscript" in scripts
    assert "//B //NoLogo" in scripts


def test_runtime_processes_use_no_window_flags() -> None:
    safe_process = (ROOT / "app/core/safe_process.py").read_text(encoding="utf-8")
    monitor = (
        ROOT / "app/gui/self_development_console.py"
    ).read_text(encoding="utf-8")
    assert "CREATE_NO_WINDOW" in safe_process
    assert "CREATE_NEW_CONSOLE" not in monitor
    assert "CREATE_NO_WINDOW" in monitor


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
