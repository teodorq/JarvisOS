"""Bounded, read-only projection of the local Forex PAPER account."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any

from app.core.project_paths import resolve_project_root


_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


class ForexPaperDashboard:
    """Expose only safe account fields required by the owner dashboard."""

    MAX_RESULT_BYTES = 2_000_000

    def __init__(self, project_root: str | Path | None, *, executor: Any) -> None:
        root = resolve_project_root(project_root)
        self.result_path = root / "data" / "trading" / "forex_paper_last.json"
        self.executor = executor

    def snapshot(self) -> dict[str, Any]:
        payload = self._load_result()
        if payload is not None:
            if not self._result_is_paper_only(payload):
                return self._blocked("Raport nie przeszedł kontroli PAPER ONLY.")
            paper = payload.get("paper")
            paper = dict(paper) if isinstance(paper, dict) else {}
            account = paper.get("account")
            account = dict(account) if isinstance(account, dict) else {}
            return self._project(
                account,
                observed_at=str(payload.get("observed_at", "")),
                source="LATEST_PAPER_CYCLE",
            )
        try:
            account = self.executor.status()
        except Exception:
            return self._blocked("Lokalna księga PAPER jest chwilowo niedostępna.")
        account = dict(account) if isinstance(account, dict) else {}
        if not self._account_is_paper_only(account):
            return self._blocked("Lokalna księga nie potwierdza trybu PAPER ONLY.")
        return self._project(account, observed_at="", source="LOCAL_PAPER_LEDGER")

    def _load_result(self) -> dict[str, Any] | None:
        try:
            size = self.result_path.stat().st_size
            if size <= 0 or size > self.MAX_RESULT_BYTES:
                return None
            value = json.loads(self.result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return dict(value) if isinstance(value, dict) else None

    @classmethod
    def _result_is_paper_only(cls, payload: dict[str, Any]) -> bool:
        paper = payload.get("paper")
        paper = dict(paper) if isinstance(paper, dict) else {}
        account = paper.get("account")
        account = dict(account) if isinstance(account, dict) else {}
        root_flags = all(
            payload.get(key) is False
            for key in ("broker_orders_sent", "live_orders_sent", "real_money_access")
        )
        paper_flags = (
            paper.get("live_orders_sent") is False
            and paper.get("network_access") is False
        )
        return root_flags and paper_flags and cls._account_is_paper_only(account)

    @staticmethod
    def _account_is_paper_only(account: dict[str, Any]) -> bool:
        return (
            str(account.get("mode", "")) == "FOREX_PAPER_ONLY"
            and account.get("live_trading_enabled") is False
            and account.get("network_access") is False
        )

    def _project(
        self,
        account: dict[str, Any],
        *,
        observed_at: str,
        source: str,
    ) -> dict[str, Any]:
        positions = self._positions(account.get("open_positions"))
        return {
            "status": "READY",
            "mode": "FOREX_PAPER_ONLY",
            "source": source,
            "observed_at": " ".join(observed_at.split())[:64],
            "balance_pln": self._number(account.get("balance_pln"), 2),
            "equity_pln": self._number(account.get("equity_pln"), 2),
            "unrealized_pnl_pln": self._number(
                account.get("unrealized_pnl_pln"), 2
            ),
            "realized_pnl_pln": self._number(account.get("realized_pnl_pln"), 2),
            "position_count": len(positions),
            "positions": positions,
            "closed_trade_count": self._count(account.get("closed_trade_count")),
            "processed_cycle_count": self._count(
                account.get("processed_cycle_count")
            ),
            "audit_chain_valid": account.get("audit_chain_valid") is True,
            "kill_switch_active": account.get("kill_switch_active") is True,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
            "message": "Lokalna symulacja; brak zleceń u brokera.",
        }

    @classmethod
    def _positions(cls, value: object) -> list[dict[str, str]]:
        items = list(value) if isinstance(value, list) else []
        result: list[dict[str, str]] = []
        for raw in items[:5]:
            item = dict(raw) if isinstance(raw, dict) else {}
            pair = str(item.get("pair", "")).strip().upper()
            side = str(item.get("side", "")).strip().upper()
            if not _PAIR.fullmatch(pair) or side not in {"LONG", "SHORT"}:
                continue
            result.append({
                "pair": pair,
                "side": side,
                "units": cls._number(item.get("units"), 0),
                "entry_price": cls._number(item.get("entry_price"), 6),
                "current_price": cls._number(item.get("current_price"), 6),
                "stop_loss": cls._number(item.get("stop_loss"), 6),
                "take_profit": cls._number(item.get("take_profit"), 6),
                "opened_at": " ".join(str(item.get("opened_at", "")).split())[:64],
            })
        return result

    @staticmethod
    def _number(value: object, places: int) -> str:
        try:
            number = Decimal(str(value))
            if not number.is_finite() or abs(number) > Decimal("1000000000000"):
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            number = Decimal("0")
        return f"{number:.{places}f}"

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, min(int(value or 0), 1_000_000))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _blocked(message: str) -> dict[str, Any]:
        return {
            "status": "BLOCKED",
            "mode": "FOREX_PAPER_ONLY",
            "positions": [],
            "position_count": 0,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
            "message": message,
        }


__all__ = ["ForexPaperDashboard"]
