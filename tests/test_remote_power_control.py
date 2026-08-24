from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import urllib.error
import urllib.request

import pytest
from PySide6.QtCore import QObject, Signal

from app.cloud.client import CloudPlannerClient, CloudPlannerSettings, CloudPlannerUnavailable
from app.cloud.contracts import (
    REMOTE_POWER_CANCEL_KIND,
    REMOTE_POWER_SHUTDOWN_KIND,
    looks_like_remote_power_command,
    normalize_remote_power_request,
)
from app.core.windows_power import WindowsPowerController
from app.gui.remote_command_runtime import RemoteCommandRuntime
from cloud_service.main import ServiceConfig, build_server
from cloud_service.phone_power_countdown import PHONE_PAGE, enhance_phone_page
from cloud_service.remote_store import MemoryRemoteCommandStore


class _Timer:
    def __init__(self, delay: float, callback) -> None:
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if not self.cancelled:
            self.callback()


class _RunResult:
    returncode = 0


def test_windows_power_uses_in_memory_countdown_without_forced_shutdown() -> None:
    with TemporaryDirectory() as temporary:
        executable = Path(temporary) / "shutdown.exe"
        executable.touch()
        timers: list[_Timer] = []
        calls: list[tuple[list[str], dict]] = []

        def timer_factory(delay, callback):
            timer = _Timer(delay, callback)
            timers.append(timer)
            return timer

        def runner(command, **options):
            calls.append((list(command), dict(options)))
            return _RunResult()

        power = WindowsPowerController(
            executable=executable,
            runner=runner,
            timer_factory=timer_factory,
            platform_name="nt",
        )

        scheduled = power.schedule_shutdown()

        assert scheduled["ok"] is True
        assert timers[0].delay == 60
        assert timers[0].daemon is True
        assert calls == []
        timers[0].fire()
        command, options = calls[0]
        assert command[1:5] == ["/s", "/t", "0", "/d"]
        assert "/f" not in command
        assert options.get("shell") is not True
        assert power.status()["last_execution"] == "STARTED"


def test_windows_power_cancel_and_close_never_start_shutdown() -> None:
    with TemporaryDirectory() as temporary:
        executable = Path(temporary) / "shutdown.exe"
        executable.touch()
        timers: list[_Timer] = []
        calls: list[list[str]] = []

        def timer_factory(delay, callback):
            timer = _Timer(delay, callback)
            timers.append(timer)
            return timer

        power = WindowsPowerController(
            executable=executable,
            runner=lambda command, **_options: calls.append(list(command)),
            timer_factory=timer_factory,
            platform_name="nt",
        )
        power.schedule_shutdown()
        result = power.cancel_shutdown()
        timers[0].fire()
        power.schedule_shutdown()
        power.close()
        timers[1].fire()

        assert result["ok"] is True
        assert calls == []
        assert power.status()["scheduled"] is False


def test_power_controller_fails_closed_outside_windows() -> None:
    power = WindowsPowerController(
        executable="shutdown.exe",
        platform_name="posix",
    )

    result = power.schedule_shutdown()

    assert result["ok"] is False
    assert power.status()["scheduled"] is False


def test_power_request_id_is_not_replayed_after_restart() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executable = root / "shutdown.exe"
        executable.touch()
        first_timers: list[_Timer] = []
        second_timers: list[_Timer] = []

        def factory(target):
            def create(delay, callback):
                timer = _Timer(delay, callback)
                target.append(timer)
                return timer
            return create

        first = WindowsPowerController(
            executable=executable,
            timer_factory=factory(first_timers),
            platform_name="nt",
            project_root=root,
        )
        request_id = "a" * 32
        assert first.execute(REMOTE_POWER_SHUTDOWN_KIND, request_id)["ok"] is True
        first.close()
        restarted = WindowsPowerController(
            executable=executable,
            timer_factory=factory(second_timers),
            platform_name="nt",
            project_root=root,
        )

        duplicate = restarted.execute(REMOTE_POWER_SHUTDOWN_KIND, request_id)

        assert duplicate["ok"] is True
        assert "już" in duplicate["message"]
        assert second_timers == []


def test_power_contract_is_exact_and_free_text_is_separated() -> None:
    assert normalize_remote_power_request({
        "action": "shutdown", "confirmation": "WYLACZ"
    }) == (REMOTE_POWER_SHUTDOWN_KIND, "Wyłączenie komputera")
    assert normalize_remote_power_request({
        "action": "cancel_shutdown"
    }) == (REMOTE_POWER_CANCEL_KIND, "Anulowanie wyłączenia komputera")
    assert looks_like_remote_power_command("Wyłącz komputer") is True
    assert looks_like_remote_power_command("status systemu") is False


class TestRemotePowerCloud:
    owner_id = "77f4b7fe-8e18-498b-8898-84befa780edb"
    desktop_token = "desktop-token-with-enough-entropy"
    legacy_phone_token = "legacy-phone-token-with-enough-entropy"
    device_id = "desktop-main"

    def setup_method(self) -> None:
        self.store = MemoryRemoteCommandStore()
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.desktop_token,
                phone_api_token=self.legacy_phone_token,
                phone_principal_id=self.owner_id,
                environment="test",
            ),
            remote_store=self.store,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.owner_headers = {
            "X-MS-CLIENT-PRINCIPAL-ID": self.owner_id,
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
        self.power_headers = {
            **self.owner_headers,
            "X-JARVIS-POWER-CONTROL": "owner-v1",
        }

    def teardown_method(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, path: str, payload: dict, headers: dict | None = None):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_owner_can_queue_short_lived_confirmed_shutdown(self) -> None:
        status, record = self._post(
            "/v1/remote/power",
            {
                "device_id": self.device_id,
                "action": "shutdown",
                "confirmation": "WYLACZ",
                "request_id": "d" * 32,
            },
            self.power_headers,
        )

        assert status == 202
        assert record["kind"] == REMOTE_POWER_SHUTDOWN_KIND
        assert record["expires_at"] - record["created_at"] == 300
        client = CloudPlannerClient(CloudPlannerSettings(
            base_url=self.base_url,
            api_token=self.desktop_token,
            timeout_seconds=2,
            remote_device_id=self.device_id,
        ))
        assert client.claim_remote_command()["kind"] == REMOTE_POWER_SHUTDOWN_KIND

    def test_missing_phrase_and_legacy_token_are_rejected(self) -> None:
        base = {"device_id": self.device_id, "action": "shutdown"}
        phrase_status, phrase = self._post(
            "/v1/remote/power", base, self.power_headers
        )
        token_status, token = self._post(
            "/v1/remote/power",
            {**base, "confirmation": "WYLACZ"},
            {
                "Authorization": f"Bearer {self.legacy_phone_token}",
                "X-JARVIS-POWER-CONTROL": "owner-v1",
            },
        )

        assert phrase_status == 422
        assert phrase["error"] == "explicit_power_confirmation_required"
        assert token_status == 401
        assert token["error"] == "owner_identity_required"
        assert self.store.claim_next(self.device_id) is None

    def test_cross_site_style_request_without_power_header_is_rejected(self) -> None:
        status, payload = self._post(
            "/v1/remote/power",
            {
                "device_id": self.device_id,
                "action": "shutdown",
                "confirmation": "WYLACZ",
            },
            self.owner_headers,
        )

        assert status == 400
        assert payload["error"] == "power_control_header_required"
        assert self.store.claim_next(self.device_id) is None

    def test_cancel_is_a_separate_reversible_power_kind(self) -> None:
        status, record = self._post(
            "/v1/remote/power",
            {"device_id": self.device_id, "action": "cancel_shutdown"},
            self.power_headers,
        )

        assert status == 202
        assert record["kind"] == REMOTE_POWER_CANCEL_KIND
        assert record["expires_at"] - record["created_at"] == 300

    def test_free_text_shutdown_is_rejected_in_favor_of_power_control(self) -> None:
        status, payload = self._post(
            "/v1/remote/commands",
            {"device_id": self.device_id, "command": "wyłącz komputer"},
            self.owner_headers,
        )

        assert status == 422
        assert payload["error"] == "dedicated_power_control_required"
        assert self.store.claim_next(self.device_id) is None


class _Window(QObject):
    client_event_signal = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []
        self.pending_thought = None

    def process_client_command(self, command: str) -> None:
        self.commands.append(command)


class _Power:
    def __init__(self) -> None:
        self.kinds: list[str] = []
        self.closed = False

    def execute(self, kind: str, request_id: str) -> dict:
        self.kinds.append(f"{kind}:{request_id}")
        return {"ok": True, "message": "Zaplanowano bezpiecznie."}

    def close(self) -> None:
        self.closed = True


class _Client:
    remote_enabled = True


def test_remote_runtime_routes_power_away_from_natural_commands() -> None:
    window = _Window()
    power = _Power()
    runtime = RemoteCommandRuntime(window, client=_Client(), power=power)
    reports: list[tuple[str, str, bool]] = []
    runtime._submit = lambda function, callback, failed=None: callback(function())
    runtime._queue_report = lambda status, message, terminal: reports.append(
        (status, message, terminal)
    )

    runtime._after_claim({
        "id": "e" * 32,
        "command": "Wyłączenie komputera",
        "kind": REMOTE_POWER_SHUTDOWN_KIND,
    })

    assert power.kinds == [f"{REMOTE_POWER_SHUTDOWN_KIND}:{'e' * 32}"]
    assert window.commands == []
    assert reports == [("completed", "Zaplanowano bezpiecznie.", True)]
    runtime.shutdown()
    assert power.closed is True


def test_phone_page_contains_two_step_power_controls() -> None:
    assert 'id="powerOpen"' in PHONE_PAGE
    assert 'id="powerPhrase"' in PHONE_PAGE
    assert 'id="powerCancel"' in PHONE_PAGE
    assert 'powerPhrase.value.trim().toUpperCase()!=="WYLACZ"' in PHONE_PAGE
    assert 'api("/v1/remote/power"' in PHONE_PAGE
    assert '"X-JARVIS-POWER-CONTROL":"owner-v1"' in PHONE_PAGE
    assert "60 sekund odliczania" in PHONE_PAGE


def test_phone_page_restores_authoritative_power_countdown() -> None:
    assert 'id="powerCountdown"' in PHONE_PAGE
    assert 'aria-live="assertive"' in PHONE_PAGE
    assert 'const powerDeadlineKey="jarvisPowerDeadline"' in PHONE_PAGE
    assert 'data.kind==="power_shutdown"' in PHONE_PAGE
    assert 'data.kind==="power_cancel"' in PHONE_PAGE
    assert "startPowerCountdown(data.updated_at)" in PHONE_PAGE
    assert "syncPowerCountdown(data)" in PHONE_PAGE
    assert "restorePowerCountdown()" in PHONE_PAGE
    assert "startedAt+60000" in PHONE_PAGE


def test_phone_countdown_template_drift_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="template anchor changed"):
        enhance_phone_page("<html></html>")


def test_cloud_deployment_gate_requires_full_source_integrity() -> None:
    workflow = Path(".github/workflows/cloud-image.yml").read_text(
        encoding="utf-8"
    )
    assert "tests/test_remote_power_control.py" in workflow
    assert "Require successful full source integrity" in workflow
    assert 'test_remote_command_bridge.py" -v' in workflow
    assert "python -m pytest" not in workflow


def test_expired_power_record_is_rejected_before_dispatch() -> None:
    client = CloudPlannerClient(CloudPlannerSettings())
    try:
        client._validate_remote_record({
            "id": "f" * 32,
            "device_id": "desktop-main",
            "command": "Wyłączenie komputera",
            "kind": REMOTE_POWER_SHUTDOWN_KIND,
            "expires_at": int(time.time()) - 1,
        })
    except CloudPlannerUnavailable as error:
        assert "expired" in str(error)
    else:
        raise AssertionError("expired power command was accepted")
