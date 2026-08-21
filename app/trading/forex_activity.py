"""Deduplicated, local-only owner notifications for Forex PAPER activity."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.market_data.forex_environment import ForexDataSettings


_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


class ForexPaperActivityFeed:
    """Turn the latest watchdog result into at most one safe UI event."""

    MAX_RESULT_BYTES = 2_000_000

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        settings: ForexDataSettings | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.result_path = root / "data" / "trading" / "forex_paper_last.json"
        self.state = JsonStore(
            root / "data" / "trading" / "forex_activity_notifications.json",
            self._default_state,
        )
        self.settings = settings or ForexDataSettings.from_environment()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "last_cycle_key": "",
            "last_health": "",
            "notification_count": 0,
        }

    def poll(self) -> dict[str, Any] | None:
        """Remember the newest cycle and return its one-time display event."""
        if not (
            self.settings.enabled
            and self.settings.paper_autopilot_enabled
            and self.settings.primary_provider == "MT5_DEMO"
        ):
            return None
        payload = self._load_result()
        if payload is None:
            return None
        cycle_key = self._cycle_key(payload)
        if not cycle_key:
            return None
        current = self._normalize_state(self.state.load())
        if current["last_cycle_key"] == cycle_key:
            return None
        health = self._health(payload)
        event = self._event(payload, previous_health=current["last_health"])
        current.update({
            "last_cycle_key": cycle_key,
            "last_health": health,
            "notification_count": int(current["notification_count"])
            + (1 if event is not None else 0),
        })
        self.state.save(current)
        return event

    def status(self) -> dict[str, Any]:
        current = self._normalize_state(self.state.load())
        return {
            "status": "FOREX_PAPER_ACTIVITY_READY",
            "enabled": bool(
                self.settings.enabled
                and self.settings.paper_autopilot_enabled
                and self.settings.primary_provider == "MT5_DEMO"
            ),
            "notification_count": current["notification_count"],
            "last_health": current["last_health"],
            "voice_notifications": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
        }

    def _load_result(self) -> dict[str, Any] | None:
        try:
            if (
                not self.result_path.is_file()
                or self.result_path.stat().st_size <= 0
                or self.result_path.stat().st_size > self.MAX_RESULT_BYTES
            ):
                return None
            value = json.loads(self.result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _cycle_key(payload: dict[str, Any]) -> str:
        cycle_id = " ".join(str(payload.get("cycle_id", "")).split())[:96]
        observed_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
        return f"{cycle_id}|{observed_at}" if cycle_id or observed_at else ""

    @staticmethod
    def _health(payload: dict[str, Any]) -> str:
        unsafe = any(
            payload.get(key) is not False
            for key in (
                "broker_orders_sent",
                "live_orders_sent",
                "real_money_access",
            )
        )
        if unsafe:
            return "SAFETY_ATTENTION"
        return (
            "HEALTHY"
            if payload.get("status") == "PAPER_CYCLE_COMPLETED"
            else "BLOCKED"
        )

    def _event(
        self,
        payload: dict[str, Any],
        *,
        previous_health: str,
    ) -> dict[str, Any] | None:
        health = self._health(payload)
        if health == "SAFETY_ATTENTION":
            return self._display(
                "important",
                "Wykryłem niespójny raport Forex PAPER. Wynik wymaga sprawdzenia "
                "w trybie właściciela; zlecenia LIVE pozostają niedostępne.",
            )
        executions = self._executions(payload)
        if executions:
            details = "; ".join(self._execution_text(item) for item in executions[:4])
            return self._display(
                "important",
                "Forex PAPER: " + details + ". To wyłącznie lokalna symulacja — "
                "nie wysłałem zlecenia do brokera.",
            )
        if health == "BLOCKED" and previous_health != "BLOCKED":
            return self._display(
                "brief",
                "Wstrzymałem nowe decyzje Forex PAPER, ponieważ bieżąca kontrola "
                "danych nie przeszła. Spróbuję ponownie automatycznie; LIVE jest "
                "niedostępny.",
            )
        if health == "HEALTHY" and previous_health == "BLOCKED":
            return self._display(
                "brief",
                "Dane Forex PAPER wróciły do prawidłowego stanu. Ponownie analizuję "
                "7 par wyłącznie w lokalnej symulacji.",
            )
        return None

    @staticmethod
    def _executions(payload: dict[str, Any]) -> list[dict[str, Any]]:
        paper = payload.get("paper")
        paper = dict(paper) if isinstance(paper, dict) else {}
        execution = paper.get("execution")
        execution = dict(execution) if isinstance(execution, dict) else {}
        return [
            dict(item)
            for item in list(execution.get("executions", []) or [])[:20]
            if isinstance(item, dict)
        ]

    @staticmethod
    def _execution_text(execution: dict[str, Any]) -> str:
        fill = execution.get("fill")
        fill = dict(fill) if isinstance(fill, dict) else {}
        action = str(fill.get("action", "")).strip().upper()
        pair = str(fill.get("pair", "")).strip().upper()
        visible_pair = pair.replace("_", "/") if _PAIR.fullmatch(pair) else "parze Forex"
        if action in {"OPEN_LONG", "OPEN_SHORT"}:
            side = action.removeprefix("OPEN_")
            return f"otworzyłem symulowaną pozycję {side} na {visible_pair}"
        if action in {"CLOSE_LONG", "CLOSE_SHORT"}:
            side = action.removeprefix("CLOSE_")
            pnl = str(fill.get("realized_pnl_pln", "0.00")).strip()[:32]
            return (
                f"zamknąłem symulowaną pozycję {side} na {visible_pair}; "
                f"wynik {pnl} PLN"
            )
        return f"wykonałem lokalną operację symulacyjną na {visible_pair}"

    @staticmethod
    def _display(state: str, message: str) -> dict[str, Any]:
        return {
            "state": state,
            "message": " ".join(message.split())[:420],
            "progress": 0,
            "requires_confirmation": False,
            "result_type": "FOREX_PAPER_ACTIVITY",
        }

    @classmethod
    def _normalize_state(cls, value: object) -> dict[str, Any]:
        result = cls._default_state()
        if isinstance(value, dict):
            result["last_cycle_key"] = str(value.get("last_cycle_key", ""))[:192]
            health = str(value.get("last_health", ""))
            result["last_health"] = (
                health if health in {"HEALTHY", "BLOCKED", "SAFETY_ATTENTION"} else ""
            )
            try:
                count = int(value.get("notification_count", 0) or 0)
            except (TypeError, ValueError):
                count = 0
            result["notification_count"] = max(0, min(count, 1_000_000))
        return result


__all__ = ["ForexPaperActivityFeed"]
