from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from app.assistant.trading_runtime import LazyTradingRuntime


def test_constructing_runtime_does_not_load_trading_center() -> None:
    code = (
        "import sys; "
        "from app.assistant.trading_runtime import LazyTradingRuntime; "
        "runtime=LazyTradingRuntime('.'); "
        "assert not runtime.loaded; "
        "assert 'app.trading.control_center' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_activity_feed_stays_light_until_full_center_is_needed() -> None:
    with TemporaryDirectory() as directory:
        runtime = LazyTradingRuntime(Path(directory))

        activity = runtime.forex_activity

        assert activity is runtime.forex_activity
        assert not runtime.loaded


def test_full_center_reuses_already_created_activity_feed() -> None:
    with TemporaryDirectory() as directory:
        runtime = LazyTradingRuntime(Path(directory))
        activity = runtime.forex_activity

        dashboard = runtime.forex_dashboard

        assert dashboard is not None
        assert runtime.loaded
        assert runtime.forex_activity is activity
