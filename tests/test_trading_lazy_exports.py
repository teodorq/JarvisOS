from __future__ import annotations

import subprocess
import sys


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )


def test_importing_trading_package_does_not_load_full_control_center() -> None:
    result = _run(
        "import sys; import app.trading; "
        "assert 'app.trading.control_center' not in sys.modules; "
        "assert 'app.trading.forex_forward_evidence' not in sys.modules"
    )

    assert result.returncode == 0, result.stderr


def test_public_trading_exports_still_resolve() -> None:
    result = _run(
        "import app.trading as trading; "
        "missing=[name for name in trading.__all__ if getattr(trading,name,None) is None]; "
        "assert not missing, missing"
    )

    assert result.returncode == 0, result.stderr


def test_lazy_export_is_cached_after_first_access() -> None:
    import app.trading as trading

    first = trading.TradingControlCenter
    second = trading.TradingControlCenter

    assert first is second
    assert trading.__dict__["TradingControlCenter"] is first
