"""Fail-closed desktop projection of the private Azure PAPER status."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import threading
import time
from typing import Any, Callable

from app.cloud.client import CloudPlannerClient


FOREX_CLOUD_STATUS_MAX_AGE_SECONDS = 7_200
FOREX_CLOUD_STATUS_REFRESH_SECONDS = 60.0
_PAIRS = {
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
}
_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_:.-]{0,159}$")


def _count(value: object, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid count")
    selected = int(value)
    if selected < 0 or selected > maximum:
        raise ValueError("invalid count")
    return selected


def _number(value: object, places: int) -> str:
    number = Decimal(str(value))
    if not number.is_finite() or abs(number) > Decimal("1000000000000"):
        raise InvalidOperation
    return f"{number:.{places}f}"


def _blocked(
    message: str,
    *,
    observed_at: str = "",
    age_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "status": "STALE_DATA_BLOCKED",
        "mode": "FOREX_PAPER_ONLY",
        "source": "AZURE_PAPER_STATUS",
        "observed_at": observed_at,
        "age_seconds": age_seconds,
        "data_fresh": False,
        "balance_pln": "—",
        "equity_pln": "—",
        "unrealized_pnl_pln": "—",
        "valuation_available": False,
        "valuation_status": "STATUS_UNAVAILABLE",
        "positions": [],
        "position_count": 0,
        "performance": {},
        "performance_review": {
            "status": "BLOCKED_STALE_PAPER_STATUS",
            "source_valid": False,
            "packet_persisted": False,
            "review_snapshot_frozen": False,
            "live_activation_ready": False,
        },
        "v2_research": {"status": "BLOCKED_STALE_PAPER_STATUS"},
        "last_runtime_cycle": {"available": False},
        "last_v3_cycle": {"available": False},
        "position_protection": {
            "available": False,
            "status": "CLOUD_STATUS_UNAVAILABLE",
            "attention_required": True,
            "stale": True,
        },
        "loss_streak_safety": {"active": False, "threshold": 3},
        "weekly_loss_safety": {"active": False},
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
        "message": message,
    }


def _position(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid position")
    pair = str(value.get("pair", "")).strip().upper()
    side = str(value.get("side", "")).strip().upper()
    if pair not in _PAIRS or side not in {"LONG", "SHORT"}:
        raise ValueError("invalid position")
    risk = str(value.get("initial_risk_pln", "")).strip()
    return {
        "pair": pair,
        "side": side,
        "units": "—",
        "entry_price": _number(value.get("entry_price"), 6),
        "current_price": _number(value.get("current_price"), 6),
        "stop_loss": _number(value.get("stop_loss"), 6),
        "take_profit": (
            _number(value.get("take_profit"), 6) if value.get("take_profit")
            not in (None, "") else "—"
        ),
        "opened_at": str(value.get("opened_at", ""))[:64],
        "initial_risk_pln": _number(risk, 2) if risk else "",
        "risk_recorded": bool(risk),
    }


def _performance(value: object) -> dict[str, Any]:
    item = dict(value) if isinstance(value, dict) else {}
    closed = _count(item.get("valid_closed_trade_count", 0))
    required = _count(item.get("minimum_closed_trades_for_review", 20))
    raw_pairs = item.get("pair_breakdown")
    pairs = dict(raw_pairs) if isinstance(raw_pairs, dict) else {}
    pair_breakdown: dict[str, dict[str, Any]] = {}
    for pair, raw in pairs.items():
        if pair not in _PAIRS or not isinstance(raw, dict):
            raise ValueError("invalid pair metrics")
        count = _count(raw.get("closed_trade_count", 0))
        pair_breakdown[pair] = {
            "closed_trade_count": count,
            "winning_trade_count": 0,
            "losing_trade_count": 0,
            "win_rate_pct": _number(raw.get("win_rate_pct", 0), 2),
            "net_realized_pnl_pln": _number(
                raw.get("net_realized_pnl_pln", 0), 2
            ),
            "average_trade_pnl_pln": _number(
                raw.get("average_trade_pnl_pln", 0), 2
            ),
            "profit_factor": (
                _number(raw.get("profit_factor"), 4)
                if raw.get("profit_factor") not in (None, "") else None
            ),
            "minimum_closed_trades_for_review": required,
            "review_status": (
                "NO_CLOSED_TRADES" if count == 0 else "COLLECTING_PAIR_SAMPLE"
            ),
        }
    factor = item.get("profit_factor")
    return {
        "valid_closed_trade_count": closed,
        "minimum_closed_trades_for_review": required,
        "average_trade_pnl_pln": _number(
            item.get("average_trade_pnl_pln", 0), 2
        ),
        "profit_factor": (
            _number(factor, 4) if factor not in (None, "") else None
        ),
        "maximum_closed_trade_drawdown_pln": _number(
            item.get("maximum_closed_trade_drawdown_pln", 0), 2
        ),
        "maximum_closed_trade_drawdown_pct": _number(
            item.get("maximum_closed_trade_drawdown_pct", 0), 2
        ),
        "pair_breakdown": pair_breakdown,
        "pair_review": {"ready_pair_count": 0},
        "evidence_valid": True,
        "performance_validated": False,
        "live_promotion_ready": False,
    }


def _runtime_reason_codes(value: object) -> dict[str, int]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("invalid runtime reasons")
    result: dict[str, int] = {}
    for raw_code, raw_count in value.items():
        code = str(raw_code).strip().upper()
        if not _CODE.fullmatch(code):
            raise ValueError("invalid runtime reason")
        count = _count(raw_count)
        if count <= 0:
            raise ValueError("invalid runtime reason count")
        result[code] = count
    return dict(sorted(result.items(), key=lambda item: (-item[1], item[0])))


def project_cloud_forex_status(
    value: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Convert the allowlisted cloud report or hide all current-state data."""

    if not isinstance(value, dict):
        return _blocked("Brak aktualnego raportu Azure PAPER.")
    observed_text = str(value.get("observed_at", "")).strip()
    try:
        observed = datetime.fromisoformat(
            observed_text.replace("Z", "+00:00")
        )
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("timezone required")
        selected_now = (now or datetime.now(timezone.utc)).astimezone(
            timezone.utc
        )
        raw_age = int(
            (selected_now - observed.astimezone(timezone.utc)).total_seconds()
        )
    except (TypeError, ValueError, OverflowError):
        return _blocked("Raport Azure PAPER ma nieprawidłowy czas odczytu.")
    age = max(0, raw_age)
    stale = bool(
        raw_age < -300
        or age > FOREX_CLOUD_STATUS_MAX_AGE_SECONDS
        or value.get("fresh") is not True
    )
    if stale:
        return _blocked(
            "Dane PAPER są nieaktualne. Pozycje ukryto do czasu świeżego "
            "potwierdzenia z Azure.",
            observed_at=observed.astimezone(timezone.utc).isoformat(),
            age_seconds=age,
        )
    if any(
        value.get(key) is not False
        for key in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ) or "PAPER" not in str(value.get("mode", "")).upper():
        return _blocked("Raport Azure nie potwierdza trybu PAPER ONLY.")
    try:
        raw_positions = value.get("v3_open_positions", [])
        if not isinstance(raw_positions, list) or len(raw_positions) > 20:
            raise ValueError("invalid positions")
        positions = [_position(item) for item in raw_positions]
        if _count(value.get("v3_position_count", 0), 20) != len(positions):
            raise ValueError("position count mismatch")
        performance = _performance(value.get("v3_performance"))
        balance = _number(value.get("v3_balance_pln"), 2)
        equity = _number(value.get("v3_equity_pln"), 2)
        unrealized = _number(value.get("v3_unrealized_pnl_pln"), 2)
        runtime_decision = str(value.get("runtime_decision", "")).strip().upper()
        if runtime_decision and not _CODE.fullmatch(runtime_decision):
            raise ValueError("invalid runtime decision")
        ready_pair_count = _count(value.get("runtime_ready_pair_count", 0), 20)
        blocked_pair_count = _count(
            value.get("runtime_blocked_pair_count", 0), 20
        )
        execution_count = _count(value.get("runtime_execution_count", 0), 20)
        runtime_reasons = _runtime_reason_codes(
            value.get("runtime_reason_codes", {})
        )
        v3_ready_pair_count = _count(
            value.get("v3_ready_pair_count", 0), 7
        )
        v3_blocked_pair_count = _count(
            value.get("v3_blocked_pair_count", 0), 7
        )
        v3_instruction_count = _count(
            value.get("v3_instruction_count", 0), 5
        )
        v3_execution_count = _count(
            value.get("v3_execution_count", 0), 5
        )
        v3_reasons = _runtime_reason_codes(
            value.get("v3_reason_codes", {})
        )
        v3_decision = str(value.get("v3_decision_status", "")).strip().upper()
        v3_status = str(
            value.get("v3_plan_observation_status", "")
        ).strip().upper()
        v3_activation_status = str(
            value.get("v3_activation_status", "")
        ).strip().upper()
        v3_activation_reason = str(
            value.get("v3_activation_reason", "")
        ).strip().upper()
        v3_plan_reason = str(
            value.get("v3_plan_reason", "")
        ).strip().upper()
        v3_simulation_reason = str(
            value.get("v3_simulation_reason", "")
        ).strip().upper()
        if any(
            code and not _CODE.fullmatch(code)
            for code in (
                v3_decision,
                v3_status,
                v3_activation_status,
                v3_activation_reason,
                v3_plan_reason,
                v3_simulation_reason,
            )
        ):
            raise ValueError("invalid V3 diagnostic code")
        if (
            v3_ready_pair_count + v3_blocked_pair_count > 7
            or v3_execution_count > v3_instruction_count
        ):
            raise ValueError("inconsistent V3 diagnostics")
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        return _blocked("Raport Azure PAPER nie przeszedł kontroli spójności.")
    closed = performance["valid_closed_trade_count"]
    required = performance["minimum_closed_trades_for_review"]
    return {
        "status": "READY",
        "mode": "FOREX_PAPER_ONLY",
        "source": "AZURE_PAPER_STATUS",
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
        "age_seconds": age,
        "data_fresh": True,
        "balance_pln": balance,
        "equity_pln": equity,
        "unrealized_pnl_pln": unrealized,
        "valuation_available": True,
        "valuation_status": "FRESH_QUOTES" if positions else "NO_OPEN_POSITIONS",
        "positions": positions,
        "position_count": len(positions),
        "performance": performance,
        "performance_review": {
            "status": "WAITING_FOR_PAPER_SAMPLE",
            "source_valid": True,
            "valid_closed_trade_count": closed,
            "minimum_closed_trades_for_review": required,
            "packet_persisted": False,
            "review_snapshot_frozen": False,
            "live_activation_ready": False,
        },
        "v2_research": {"status": "CLOUD_STATUS_READ_ONLY"},
        "last_runtime_cycle": {
            "available": True,
            "status": str(value.get("status", ""))[:80],
            "decision": runtime_decision or str(value.get("reason", ""))[:80],
            "ready_pair_count": ready_pair_count,
            "blocked_pair_count": blocked_pair_count,
            "execution_count": execution_count,
            "reason_codes": runtime_reasons,
            "high_impact_event_window": (
                value.get("runtime_high_impact_event_window") is True
            ),
            "live_orders_sent": False,
            "real_money_access": False,
        },
        "last_v3_cycle": {
            "available": True,
            "activation_status": v3_activation_status,
            "activation_reason": v3_activation_reason,
            "status": v3_status,
            "plan_reason": v3_plan_reason,
            "decision": v3_decision,
            "simulation_reason": v3_simulation_reason,
            "ready_pair_count": v3_ready_pair_count,
            "blocked_pair_count": v3_blocked_pair_count,
            "instruction_count": v3_instruction_count,
            "execution_count": v3_execution_count,
            "reason_codes": v3_reasons,
            "paper_orders_sent": v3_execution_count > 0,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        },
        "position_protection": {
            "available": True,
            "status": "AZURE_PAPER_STATUS_FRESH",
            "attention_required": False,
            "stale": False,
        },
        "loss_streak_safety": {"active": False, "threshold": 3},
        "weekly_loss_safety": {"active": False},
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
        "message": "Aktualny raport Azure PAPER; brak zleceń u brokera.",
    }


class CloudForexStatusSource:
    """Refresh the private status off the UI thread and cache it briefly."""

    def __init__(
        self,
        client: CloudPlannerClient | None = None,
        *,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client or CloudPlannerClient()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self._lock = threading.Lock()
        self._latest: dict[str, Any] | None = None
        self._last_attempt = float("-inf")
        self._refreshing = False

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    def snapshot(self) -> dict[str, Any] | None:
        if not self.is_configured:
            return None
        self._start_refresh_if_due()
        with self._lock:
            latest = deepcopy(self._latest)
        if latest is None:
            return _blocked(
                "Czekam na aktualne potwierdzenie Azure PAPER. Stare pozycje "
                "pozostają ukryte."
            )
        return project_cloud_forex_status(latest, now=self.now())

    def refresh_now(self) -> None:
        try:
            value = self.client.forex_status()
        except Exception:
            value = None
        with self._lock:
            if isinstance(value, dict):
                self._latest = deepcopy(value)
            self._last_attempt = self.monotonic()
            self._refreshing = False

    def _start_refresh_if_due(self) -> None:
        with self._lock:
            due = (
                self.monotonic() - self._last_attempt
                >= FOREX_CLOUD_STATUS_REFRESH_SECONDS
            )
            if self._refreshing or not due:
                return
            self._refreshing = True
            self._last_attempt = self.monotonic()
        threading.Thread(
            target=self.refresh_now,
            name="jarvis-forex-cloud-status",
            daemon=True,
        ).start()


__all__ = [
    "CloudForexStatusSource",
    "FOREX_CLOUD_STATUS_MAX_AGE_SECONDS",
    "project_cloud_forex_status",
]
