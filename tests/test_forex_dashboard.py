from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.trading.forex_dashboard import ForexPaperDashboard


class _Executor:
    def __init__(self, value: dict) -> None:
        self.value = value

    def status(self) -> dict:
        return dict(self.value)


def _account() -> dict:
    return {
        "mode": "FOREX_PAPER_ONLY",
        "live_trading_enabled": False,
        "network_access": False,
        "balance_pln": "100000.00",
        "equity_pln": "99998.12",
        "unrealized_pnl_pln": "-1.88",
        "realized_pnl_pln": "0",
        "position_count": 1,
        "open_positions": [{
            "pair": "USD_CHF",
            "side": "SHORT",
            "units": "2714",
            "entry_price": "0.799040",
            "current_price": "0.799040",
            "stop_loss": "0.800040",
            "take_profit": "0.797040",
            "opened_at": "2026-08-21T10:09:38+00:00",
        }],
        "closed_trade_count": 0,
        "performance": {
            "status": "COLLECTING_PAPER_SAMPLE",
            "valid_closed_trade_count": 1,
            "minimum_closed_trades_for_review": 20,
            "sample_progress_pct": "5.00",
            "average_trade_pnl_pln": "-44.26",
            "profit_factor": "0.0000",
            "maximum_closed_trade_drawdown_pln": "44.26",
            "maximum_closed_trade_drawdown_pct": "0.04",
            "maximum_consecutive_losses": 1,
            "pair_breakdown": {
                "USD_CHF": {
                    "closed_trade_count": 1,
                    "winning_trade_count": 0,
                    "losing_trade_count": 1,
                    "win_rate_pct": "0.00",
                    "net_realized_pnl_pln": "-44.26",
                    "average_trade_pnl_pln": "-44.26",
                    "profit_factor": "0.0000",
                    "minimum_closed_trades_for_review": 20,
                    "remaining_closed_trades_for_review": 19,
                    "sample_progress_pct": "5.00",
                    "review_status": "COLLECTING_PAIR_SAMPLE",
                },
            },
            "integrity": {"evidence_valid": True},
        },
        "processed_cycle_count": 75,
        "audit_chain_valid": True,
        "kill_switch_active": False,
        "loss_streak_safety": {
            "active": True,
            "code": "CONSECUTIVE_LOSS_COOLDOWN",
            "current_consecutive_losses": 3,
            "threshold": 3,
            "cooldown_minutes": 360,
            "resume_at": "2026-08-21T16:09:38+00:00",
            "remaining_seconds": 10800,
            "paper_only": True,
        },
    }


def _write_result(root: Path, account: dict, *, live: bool = False) -> None:
    path = root / "data" / "trading" / "forex_paper_last.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "status": "PAPER_CYCLE_COMPLETED",
        "observed_at": "2026-08-21T10:09:38+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": live,
        "real_money_access": False,
        "paper": {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "network_access": False,
            "account": account,
        },
    }), encoding="utf-8")


def test_dashboard_projects_latest_safe_paper_cycle() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        dashboard = ForexPaperDashboard(root, executor=_Executor({}))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["position_count"] == 1
        assert snapshot["positions"][0] == {
            "pair": "USD_CHF",
            "side": "SHORT",
            "units": "2714",
            "entry_price": "0.799040",
            "current_price": "0.799040",
            "stop_loss": "0.800040",
            "take_profit": "0.797040",
            "opened_at": "2026-08-21T10:09:38+00:00",
        }
        assert snapshot["unrealized_pnl_pln"] == "-1.88"
        assert snapshot["performance"]["valid_closed_trade_count"] == 1
        assert snapshot["performance"]["profit_factor"] == "0.0000"
        assert snapshot["performance"]["evidence_valid"] is True
        assert snapshot["performance"]["live_promotion_ready"] is False
        pair = snapshot["performance"]["pair_breakdown"]["USD_CHF"]
        assert pair["closed_trade_count"] == 1
        assert pair["net_realized_pnl_pln"] == "-44.26"
        assert pair["profit_factor"] == "0.0000"
        assert pair["performance_validated"] is False
        assert pair["review_status"] == "COLLECTING_PAIR_SAMPLE"
        assert pair["sample_progress_pct"] == "5.00"
        assert snapshot["performance"]["pair_review"]["ready_pair_count"] == 0
        assert snapshot["performance"]["pair_review"]["collecting_pairs"] == [
            "USD_CHF"
        ]
        assert snapshot["performance"]["pair_review"]["unobserved_pair_count"] == 6
        assert snapshot["performance"]["pair_review"]["automatic_pair_disable"] is False
        assert snapshot["new_entries_paused_by_loss_streak"] is True
        assert snapshot["loss_streak_safety"] == {
            "active": True,
            "code": "CONSECUTIVE_LOSS_COOLDOWN",
            "current_consecutive_losses": 3,
            "threshold": 3,
            "cooldown_minutes": 360,
            "resume_at": "2026-08-21T16:09:38+00:00",
            "remaining_seconds": 10800,
            "paper_only": True,
        }
        assert "wstrzymane" in snapshot["message"]
        assert snapshot["live_orders_sent"] is False


def test_dashboard_blocks_result_that_claims_live_execution() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account(), live=True)
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "BLOCKED"
        assert snapshot["positions"] == []
        assert snapshot["live_orders_sent"] is False


def test_dashboard_uses_safe_local_ledger_when_result_is_missing() -> None:
    with TemporaryDirectory() as temporary:
        dashboard = ForexPaperDashboard(
            Path(temporary), executor=_Executor(_account())
        )

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["source"] == "LOCAL_PAPER_LEDGER"
        assert snapshot["position_count"] == 1


def test_dashboard_drops_invalid_positions_and_numbers() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        account = _account()
        account["equity_pln"] = "NaN"
        account["balance_pln"] = "1e999999"
        account["open_positions"] = [{"pair": "BAD", "side": "BUY"}]
        _write_result(root, account)

        snapshot = ForexPaperDashboard(root, executor=_Executor({})).snapshot()

        assert snapshot["equity_pln"] == "0.00"
        assert snapshot["balance_pln"] == "0.00"
        assert snapshot["positions"] == []
        assert snapshot["position_count"] == 0
