from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.core.windows_autostart import autostart_status, set_autostart


ROOT = Path(__file__).resolve().parents[1]


def _result(*, stdout: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_autostart_status_reads_locale_independent_json() -> None:
    with patch("app.core.windows_autostart.os.name", "nt"), patch(
        "app.core.windows_autostart._powershell",
        return_value=_result(stdout='{"installed":true,"state":"Running"}\n'),
    ):
        result = autostart_status()

    assert result == {
        "supported": True,
        "installed": True,
        "state": "RUNNING",
    }


def test_set_autostart_uses_hidden_installer_without_starting_app(tmp_path) -> None:
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    installer = tools / "install_jarvis_autostart.ps1"
    installer.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_powershell(arguments, *, timeout):
        calls.append(list(arguments))
        if arguments[0] == "-Command":
            return _result(stdout='{"installed":true,"state":"Ready"}\n')
        return _result()

    with patch("app.core.windows_autostart.os.name", "nt"), patch(
        "app.core.windows_autostart._powershell", side_effect=fake_powershell
    ):
        result = set_autostart(tmp_path, enabled=True)

    assert "-NoStart" in calls[0]
    assert "-Remove" not in calls[0]
    assert result["installed"] is True
    assert result["enabled"] is True


def test_set_autostart_removes_task_when_disabled(tmp_path) -> None:
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "install_jarvis_autostart.ps1").write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_powershell(arguments, *, timeout):
        calls.append(list(arguments))
        if arguments[0] == "-Command":
            return _result(stdout='{"installed":false,"state":"NOT_INSTALLED"}\n')
        return _result()

    with patch("app.core.windows_autostart.os.name", "nt"), patch(
        "app.core.windows_autostart._powershell", side_effect=fake_powershell
    ):
        result = set_autostart(tmp_path, enabled=False)

    assert "-Remove" in calls[0]
    assert result["installed"] is False
    assert result["enabled"] is False


def test_autostart_runs_only_at_sign_in() -> None:
    installer = (ROOT / "tools" / "install_jarvis_autostart.ps1").read_text(
        encoding="utf-8"
    )
    assert "New-ScheduledTaskTrigger -AtLogOn" in installer
    assert "RepetitionInterval" not in installer
    assert "-Trigger $trigger" in installer
    assert "System32\\wscript.exe" in installer
    assert "//B //NoLogo" in installer
    assert "-Hidden" in installer
    assert "[switch]$NoStart" in installer
    assert "if (-not $NoStart)" in installer
    hidden_runner = (ROOT / "tools" / "run_hidden_powershell.vbs").read_text(
        encoding="utf-8"
    )
    assert "shell.Run(command, 0, True)" in hidden_runner
    assert "-WindowStyle Hidden" in hidden_runner


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
    safe_process = (ROOT / "app/core/safe_process.py").read_text(
        encoding="utf-8"
    )
    monitor = (ROOT / "app/gui/self_development_console.py").read_text(
        encoding="utf-8"
    )
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
