from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer

from app.gui.client_background_reads import submit_client_read


def test_client_read_returns_before_slow_operation_finishes() -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    window = QObject()
    loop = QEventLoop()
    results = []

    def slow_read():
        time.sleep(0.25)
        return {"ready": True}

    started = time.perf_counter()
    accepted = submit_client_read(
        window,
        slow_read,
        lambda result: (results.append(result), loop.quit()),
        lambda error: (results.append(error), loop.quit()),
    )
    submit_elapsed = time.perf_counter() - started
    QTimer.singleShot(2000, loop.quit)
    loop.exec()

    assert app is not None
    assert accepted is True
    assert submit_elapsed < 0.15
    assert results == [{"ready": True}]


def test_client_read_lane_rejects_overlapping_network_work() -> None:
    QCoreApplication.instance() or QCoreApplication([])
    window = QObject()
    loop = QEventLoop()
    results = []

    first = submit_client_read(
        window,
        lambda: (time.sleep(0.15), "first")[1],
        lambda result: (results.append(result), loop.quit()),
        lambda error: (results.append(error), loop.quit()),
    )
    second = submit_client_read(
        window, lambda: "second", results.append, results.append,
    )
    QTimer.singleShot(2000, loop.quit)
    loop.exec()

    assert first is True
    assert second is False
    assert results == ["first"]
