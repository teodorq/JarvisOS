from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtNetwork import QLocalServer, QLocalSocket


INSTANCE_SERVER_NAME = "JARVIS_OS_DESKTOP_INSTANCE_V1"


def force_visible_start(arguments: Iterable[object]) -> bool:
    return any(
        str(argument).strip().casefold() == "--show"
        for argument in arguments
    )


def request_existing_instance(
    command: str,
    *,
    server_name: str = INSTANCE_SERVER_NAME,
    timeout_ms: int = 400,
) -> bool:
    """Send a small command to the running desktop instance, if present."""
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(max(50, int(timeout_ms))):
        socket.abort()
        return False
    payload = (str(command).strip().casefold() or "ping") + "\n"
    socket.write(payload.encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(max(50, int(timeout_ms)))
    socket.disconnectFromServer()
    return True


def create_instance_server(
    *,
    server_name: str = INSTANCE_SERVER_NAME,
) -> QLocalServer | None:
    """Create the local command endpoint, recovering a stale endpoint."""
    server = QLocalServer()
    if server.listen(server_name):
        return server
    QLocalServer.removeServer(server_name)
    if server.listen(server_name):
        return server
    return None


def install_instance_handler(
    server: QLocalServer,
    *,
    on_show: Callable[[], None],
) -> None:
    """Show the existing window when another launcher sends ``show``."""

    def accept_connections() -> None:
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            if socket is None:
                break

            def consume(active_socket: QLocalSocket = socket) -> None:
                payload = bytes(active_socket.readAll()).decode(
                    "utf-8", errors="ignore"
                )
                commands = {
                    line.strip().casefold()
                    for line in payload.splitlines()
                    if line.strip()
                }
                if "show" in commands:
                    on_show()
                active_socket.disconnectFromServer()
                active_socket.deleteLater()

            socket.readyRead.connect(consume)
            if socket.bytesAvailable() > 0:
                consume()

    server.newConnection.connect(accept_connections)


__all__ = [
    "INSTANCE_SERVER_NAME",
    "create_instance_server",
    "force_visible_start",
    "install_instance_handler",
    "request_existing_instance",
]
