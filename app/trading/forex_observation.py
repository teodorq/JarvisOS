"""Tamper-evident Forex observation cycles that never execute an order."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import TYPE_CHECKING, Any, Mapping

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import MAJOR_FOREX_PAIRS, ForexQuote
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.models import TradingValidationError, aware_utc

if TYPE_CHECKING:
    from app.market_data.forex_gateway import ForexReadOnlyDataGateway


_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")
_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _shared_lock(path: Path) -> threading.RLock:
    key = str(path).casefold()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _safe_reason(error: Exception) -> str:
    raw = str(error or "DATA_SOURCE_FAILURE").upper()
    cleaned = re.sub(r"[^A-Z0-9_:.-]+", "_", raw).strip("_")
    return cleaned[:160] or "DATA_SOURCE_FAILURE"


class ForexObservationJournal:
    """Store bounded observation evidence separately from the paper ledger."""

    MAX_OBSERVATIONS = 10_000
    MINIMUM_MARKET_OPEN_OBSERVATIONS = 20
    MINIMUM_MARKET_DAYS = 3

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "forex_observations.json"
        self.store = JsonStore(self.path, self._default)
        self._lock = _shared_lock(self.path)

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": "FOREX_OBSERVATION_ONLY",
            "observations": [],
        }

    def record(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        selected = deepcopy(dict(observation))
        observation_id = str(selected.get("observation_id", ""))
        if not _OBSERVATION_ID.fullmatch(observation_id):
            raise TradingValidationError("forex_observation: invalid_id")
        if selected.get("mode") != "FOREX_OBSERVATION_ONLY":
            raise TradingValidationError("forex_observation: invalid_mode")
        if bool(selected.get("paper_orders_sent")) or bool(
            selected.get("live_orders_sent")
        ):
            raise TradingValidationError("forex_observation: order_flag_forbidden")
        with self._lock:
            state = self._normalized(self.store.load())
            if not self.verify(state):
                raise TradingValidationError("forex_observation: audit_chain_invalid")
            for previous in state["observations"]:
                if previous.get("observation_id") == observation_id:
                    replay = deepcopy(previous)
                    replay["idempotent_replay"] = True
                    return replay
            observations = list(state["observations"])
            selected["sequence"] = len(observations) + 1
            selected["previous_hash"] = (
                str(observations[-1].get("observation_hash", ""))
                if observations else ""
            )
            selected["observation_hash"] = self._hash(selected)
            observations.append(selected)
            if len(observations) > self.MAX_OBSERVATIONS:
                observations = self._rehash(
                    observations[-self.MAX_OBSERVATIONS:]
                )
            state["observations"] = observations
            self.store.save(state)
            saved = deepcopy(observations[-1])
            saved["idempotent_replay"] = False
            return saved

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._normalized(self.store.load()))

    def summary(self) -> dict[str, Any]:
        state = self.snapshot()
        observations = state["observations"]
        completed = [
            item for item in observations
            if item.get("status") == "OBSERVATION_RECORDED"
        ]
        qualified = [
            item for item in completed
            if item.get("market_open") is True
            and item.get("fully_cross_checked") is True
        ]
        market_days = {
            str(item.get("observed_at", ""))[:10]
            for item in qualified
            if str(item.get("observed_at", ""))
        }
        audit_valid = self.verify(state)
        promotion_ready = (
            audit_valid
            and len(qualified) >= self.MINIMUM_MARKET_OPEN_OBSERVATIONS
            and len(market_days) >= self.MINIMUM_MARKET_DAYS
        )
        return {
            "status": "READY" if audit_valid else "BLOCKED",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_count": len(observations),
            "completed_count": len(completed),
            "blocked_count": len(observations) - len(completed),
            "qualified_market_open_count": len(qualified),
            "qualified_market_day_count": len(market_days),
            "minimum_market_open_observations": (
                self.MINIMUM_MARKET_OPEN_OBSERVATIONS
            ),
            "minimum_market_days": self.MINIMUM_MARKET_DAYS,
            "paper_promotion_ready": promotion_ready,
            "automatic_promotion": False,
            "audit_chain_valid": audit_valid,
            "latest_observation_id": (
                str(observations[-1].get("observation_id", ""))
                if observations else ""
            ),
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    @classmethod
    def verify(cls, state: Mapping[str, Any]) -> bool:
        if state.get("mode") != "FOREX_OBSERVATION_ONLY":
            return False
        previous_hash = ""
        for sequence, raw in enumerate(list(state.get("observations", []) or []), 1):
            item = dict(raw or {})
            if int(item.get("sequence", 0) or 0) != sequence:
                return False
            if str(item.get("previous_hash", "")) != previous_hash:
                return False
            expected = cls._hash(item)
            if str(item.get("observation_hash", "")) != expected:
                return False
            previous_hash = expected
        return True

    @classmethod
    def _rehash(cls, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        previous_hash = ""
        for sequence, raw in enumerate(observations, 1):
            item = deepcopy(raw)
            item["sequence"] = sequence
            item["previous_hash"] = previous_hash
            item["observation_hash"] = cls._hash(item)
            previous_hash = item["observation_hash"]
            result.append(item)
        return result

    @staticmethod
    def _hash(observation: Mapping[str, Any]) -> str:
        payload = {
            key: value
            for key, value in dict(observation).items()
            if key not in {"observation_hash", "idempotent_replay"}
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _normalized(self, value: object) -> dict[str, Any]:
        state = self._default()
        if isinstance(value, dict):
            state["mode"] = str(value.get("mode", ""))
            state["observations"] = [
                dict(item) for item in list(value.get("observations", []) or [])
                if isinstance(item, dict)
            ]
        return state


class ForexObservationService:
    """Collect, assess and plan once, stopping before execution."""

    def __init__(
        self,
        project_root: str | Path | None,
        *,
        gateway: ForexReadOnlyDataGateway,
        policy: ForexPaperPolicy | None = None,
        journal: ForexObservationJournal | None = None,
        executor: ForexPaperExecutionEngine | None = None,
    ) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.gateway = gateway
        self.journal = journal or ForexObservationJournal(project_root)
        self.executor = executor or ForexPaperExecutionEngine(
            project_root, policy=self.policy
        )
        self.scanner = ForexMarketScanner(MAJOR_FOREX_PAIRS)
        self.coordinator = ForexPaperCoordinator(self.policy)

    def observe_once(
        self,
        *,
        observation_id: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_id = str(observation_id or "").strip()
        if not _OBSERVATION_ID.fullmatch(selected_id):
            raise TradingValidationError("forex_observation: invalid_id")
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        positions_before = self.executor.positions()
        try:
            bundle = self.gateway.collect(now=selected_now)
            all_quotes: dict[str, ForexQuote] = dict(bundle.quotes)
            for quote in bundle.conversion_quotes:
                if quote.pair.symbol in all_quotes:
                    raise TradingValidationError(
                        "forex_observation: duplicate_conversion_quote"
                    )
                all_quotes[quote.pair.symbol] = quote
            rates = ForexRateBook(
                all_quotes.values(),
                now=selected_now,
                max_age_seconds=self.policy.max_conversion_age_seconds,
            )
            positions = self.executor.positions()
            assessments = self.scanner.scan(
                quotes=bundle.quotes,
                bars=bundle.bars,
                contexts=bundle.contexts,
                positions={
                    symbol: position.side
                    for symbol, position in positions.items()
                },
                now=selected_now,
            )
            account = self.executor.status(quotes=bundle.quotes, rates=rates)
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes=bundle.quotes,
                positions=positions,
                rates=rates,
                equity_pln=account["equity_pln"],
                daily_pnl_pln=account["daily_pnl_pln"],
                now=selected_now,
            )
            diagnostics = self._diagnostics(bundle.diagnostics)
            market_open = bool(bundle.contexts) and all(
                context.market_open for context in bundle.contexts.values()
            )
            opening_blocks = sorted({
                code
                for context in bundle.contexts.values()
                for code in context.opening_blocks
            })
            instructions = list(plan.get("instructions", []) or [])
            positions_after = self.executor.positions()
            record = {
                "status": "OBSERVATION_RECORDED",
                "mode": "FOREX_OBSERVATION_ONLY",
                "observation_id": selected_id,
                "observed_at": selected_now.isoformat(),
                "market_open": market_open,
                "fully_cross_checked": (
                    diagnostics["cross_checked_pair_count"] == len(MAJOR_FOREX_PAIRS)
                ),
                "opening_blocks": opening_blocks,
                "data": diagnostics,
                "assessments": [item.as_dict() for item in assessments],
                "proposed_plan": plan,
                "proposed_instruction_count": len(instructions),
                "would_open_count": sum(
                    str(item.get("action", "")).startswith("OPEN_")
                    for item in instructions
                ),
                "would_close_count": sum(
                    item.get("action") == "CLOSE_POSITION"
                    for item in instructions
                ),
                "execution": {
                    "status": "NOT_EXECUTED",
                    "reason": "OBSERVATION_ONLY",
                },
                "position_count_before": len(positions_before),
                "position_count_after": len(positions_after),
                "positions_unchanged": positions_before == positions_after,
                "paper_orders_sent": False,
                "live_orders_sent": False,
                "order_network_access": False,
                "market_data_network_access": True,
            }
        except Exception as error:
            if not isinstance(error, (TradingValidationError, OSError, RuntimeError)):
                raise
            positions_after = self.executor.positions()
            record = self._blocked(
                selected_id,
                selected_now,
                _safe_reason(error),
                before=len(positions_before),
                after=len(positions_after),
                unchanged=positions_before == positions_after,
            )
        if not record["positions_unchanged"]:
            raise TradingValidationError("forex_observation: position_state_changed")
        return self.journal.record(record)

    @staticmethod
    def _diagnostics(value: Mapping[str, object]) -> dict[str, object]:
        cross_checked = tuple(
            str(item)
            for item in list(value.get("cross_checked_pairs", ()) or ())
        )
        return {
            "primary_provider": str(value.get("primary_provider", "")),
            "primary_pair_count": int(value.get("primary_pair_count", 0) or 0),
            "cross_checked_pair_count": len(cross_checked),
            "calendar_ready": bool(value.get("calendar_ready")),
            "high_impact_event_count": int(
                value.get("high_impact_event_count", 0) or 0
            ),
            "nbp_effective_date": str(value.get("nbp_effective_date", "")),
            "pln_conversion_ready": bool(value.get("pln_conversion_ready")),
        }

    @staticmethod
    def _blocked(
        observation_id: str,
        now: datetime,
        reason: str,
        *,
        before: int,
        after: int,
        unchanged: bool,
    ) -> dict[str, Any]:
        return {
            "status": "DATA_BLOCKED",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_id": observation_id,
            "observed_at": now.isoformat(),
            "market_open": False,
            "fully_cross_checked": False,
            "opening_blocks": [reason],
            "data": {},
            "assessments": [],
            "proposed_plan": {},
            "proposed_instruction_count": 0,
            "would_open_count": 0,
            "would_close_count": 0,
            "execution": {"status": "NOT_EXECUTED", "reason": reason},
            "position_count_before": before,
            "position_count_after": after,
            "positions_unchanged": unchanged,
            "paper_orders_sent": False,
            "live_orders_sent": False,
            "order_network_access": False,
            "market_data_network_access": True,
        }


__all__ = ["ForexObservationJournal", "ForexObservationService"]
