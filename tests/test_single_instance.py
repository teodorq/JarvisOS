from __future__ import annotations

from app.gui import single_instance


def test_show_flag_forces_a_visible_manual_start() -> None:
    assert single_instance.force_visible_start(["--show"]) is True
    assert single_instance.force_visible_start([" --SHOW "]) is True
    assert single_instance.force_visible_start([]) is False


def test_existing_instance_receives_show_command(monkeypatch) -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.server_name = ""
            self.payload = b""
            self.disconnected = False

        def connectToServer(self, server_name: str) -> None:
            self.server_name = server_name

        def waitForConnected(self, timeout_ms: int) -> bool:
            return timeout_ms > 0

        def write(self, payload: bytes) -> None:
            self.payload = payload

        def flush(self) -> None:
            return None

        def waitForBytesWritten(self, timeout_ms: int) -> bool:
            return timeout_ms > 0

        def disconnectFromServer(self) -> None:
            self.disconnected = True

        def abort(self) -> None:
            raise AssertionError("connected socket should not be aborted")

    socket = FakeSocket()
    monkeypatch.setattr(single_instance, "QLocalSocket", lambda: socket)

    assert single_instance.request_existing_instance("show") is True
    assert socket.server_name == single_instance.INSTANCE_SERVER_NAME
    assert socket.payload == b"show\n"
    assert socket.disconnected is True


def test_missing_instance_is_reported_without_startup_error(monkeypatch) -> None:
    class MissingSocket:
        def connectToServer(self, server_name: str) -> None:
            return None

        def waitForConnected(self, timeout_ms: int) -> bool:
            return False

        def abort(self) -> None:
            self.aborted = True

    socket = MissingSocket()
    socket.aborted = False
    monkeypatch.setattr(single_instance, "QLocalSocket", lambda: socket)

    assert single_instance.request_existing_instance("ping") is False
    assert socket.aborted is True
