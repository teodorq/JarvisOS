from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.natural_actions.day_quality import IntelligentDayQuality
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.proactive_day import ProactiveDayAnalyzer


class DailyIntelligenceService:
    """B156-B160 useful daily brief, priority, planning and completion memory."""

    INTENTS = {
        "day_overview",
        "day_priority",
        "day_plan_tomorrow",
        "day_history",
        "day_mark_done",
    }
    READ_ONLY = {
        "day_overview",
        "day_priority",
        "day_plan_tomorrow",
        "day_history",
    }

    def __init__(self, context: Any, online: Any) -> None:
        self.context = context
        self.online = online
        root = resolve_project_root(getattr(online, "project_root", None))
        self.store = JsonStore(
            root / "data" / "daily_intelligence" / "memory.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"version": "1.0", "completed": [], "updated_at": ""}

    def prepare(self, request: NaturalActionRequest) -> None:
        request.read_only = request.intent in self.READ_ONLY
        request.missing = []
        if request.intent != "day_mark_done":
            return
        item = self._clean(request.slots.get("item_text"))
        if not item:
            request.missing = ["item_text"]
            request.clarification = "Co mam oznaczyć jako zrobione?"
            return
        request.slots["item_text"] = item
        request.confirmation = f"Oznaczyć „{item}” jako zrobione?"

    def execute(self, request: NaturalActionRequest) -> str:
        if request.intent == "day_overview":
            return self._overview(self._snapshot(0))
        if request.intent == "day_priority":
            return self._priority_response(self._snapshot(0))
        if request.intent == "day_plan_tomorrow":
            return self._tomorrow_plan(self._snapshot(1))
        if request.intent == "day_history":
            return self._history()
        if request.intent == "day_mark_done":
            return self._mark_done(str(request.slots["item_text"]))
        raise ValueError("Nie mam bezpiecznej obsługi tego polecenia dnia.")

    def status(self) -> dict[str, Any]:
        data = self._load()
        return {
            "status": "INTELLIGENT_DAY_READY",
            "completed_count": len(list(data.get("completed", []) or [])),
            "writes_require_confirmation": True,
            "automatic_calendar_changes": False,
        }

    def _snapshot(self, day_offset: int) -> dict[str, Any]:
        now = datetime.now().astimezone()
        day = now.date() + timedelta(days=day_offset)
        start = datetime.combine(day, time.min, tzinfo=now.tzinfo)
        end = start + timedelta(days=1)
        events = self._safe(
            lambda: self.online.calendar.find_events(
                "", start_at=start, end_at=end, max_results=20
            ),
            [],
        )
        mail = self._safe(lambda: self.online.gmail.priority(5), [])
        reminder_status = self._safe(lambda: self.online.reminders.status(), {})
        events = sorted(
            [dict(item) for item in list(events or [])],
            key=lambda item: str(item.get("start_at", "")),
        )
        return {
            "day_offset": day_offset,
            "day": day,
            "now": now,
            "events": events,
            "mail": IntelligentDayQuality.rank_mail(
                [dict(item) for item in list(mail or [])]
            ),
            "reminders": dict(reminder_status or {}),
            "completed": self._completed_for(day),
        }

    def _overview(self, snapshot: dict[str, Any]) -> str:
        priority = self._priority(snapshot)
        mail = list(snapshot["mail"])
        mail_subject = self._mail_subject(mail[0]) if mail else ""
        details: list[str] = []
        if priority and mail_subject not in priority:
            details.append(f"Najważniejsze teraz: {priority}.")
        events = list(snapshot["events"])
        if events:
            next_event = events[0]
            details.append(
                f"Najbliżej masz „{self._title(next_event)}” "
                f"{self._moment(next_event.get('start_at'))}."
            )
            if len(events) > 1:
                details.append(
                    "Łącznie masz dzisiaj "
                    + IntelligentDayQuality.event_count(len(events))
                    + "."
                )
        else:
            details.append("Nie masz dziś zaplanowanych wydarzeń.")
        if mail:
            details.append(
                f"Wiadomość wymagająca uwagi: „{mail_subject}”."
            )
        due = self._count(snapshot["reminders"].get("due_count"))
        if due:
            details.append(
                "Masz " + IntelligentDayQuality.reminder_count(due) + "."
            )
        completed = list(snapshot["completed"])
        if completed:
            details.append(
                "Dzisiaj: "
                + IntelligentDayQuality.completed_count(len(completed))
                + "."
            )
        if not priority and not mail and not due:
            details.append("Możesz wybrać jeden najważniejszy cel i od niego zacząć.")
        return "Twój dzień: " + " ".join(details)

    def _priority_response(self, snapshot: dict[str, Any]) -> str:
        priority = self._priority(snapshot)
        if priority:
            return (
                f"Teraz zajmij się: {priority}. "
                "Gdy skończysz, powiedz mi, że to zrobione."
            )
        return (
            "Nie widzę pilnej sprawy. Wybierz jedno zadanie, które najbardziej "
            "przybliży Cię dziś do celu."
        )

    def _tomorrow_plan(self, snapshot: dict[str, Any]) -> str:
        events = list(snapshot["events"])
        mail = list(snapshot["mail"])
        steps: list[str] = []
        for event in events[:3]:
            steps.append(
                f"{self._clock(event.get('start_at'))} — {self._title(event)}"
            )
        if mail:
            moment = "rano" if not events else "po ostatnim wydarzeniu"
            steps.append(
                f"{moment} — sprawdź wiadomość „{self._mail_subject(mail[0])}”"
            )
        if not events:
            steps.insert(0, "rano — ustal jeden główny cel na dzień")
        if len(steps) < 2:
            steps.append(
                "pierwszy blok pracy — wykonaj najważniejsze zadanie bez rozpraszaczy"
            )
        steps.append(
            "wieczorem — podsumuj dzień i zapisz pierwszy krok na kolejny dzień"
        )
        items = [f"{number}. {text}" for number, text in enumerate(steps, 1)]
        return (
            "Plan na jutro: " + "; ".join(items)
            + ". Plan pozostaje bez automatycznych zmian w kalendarzu."
        )

    def _history(self) -> str:
        today = datetime.now().astimezone().date()
        completed = self._completed_for(today)
        actions = self._actions_for(today)
        labels = [str(item.get("text", "")) for item in completed]
        labels.extend(actions)
        unique = []
        for label in labels:
            clean = self._clean(label)
            if clean and clean not in unique:
                unique.append(clean)
        if not unique:
            return "Nie mam jeszcze zapisanych zakończonych spraw z dzisiaj."
        return "Dzisiaj zakończyłeś: " + "; ".join(unique[:8]) + "."

    def _mark_done(self, item: str) -> str:
        data = self._load()
        completed = list(data.get("completed", []) or [])
        now = datetime.now().astimezone()
        completed.append({
            "text": self._clean(item),
            "created_at": now.isoformat(),
            "day": now.date().isoformat(),
        })
        data["completed"] = completed[-365:]
        data["updated_at"] = now.isoformat()
        self.store.save(data)
        return f"Oznaczyłem „{self._clean(item)}” jako zrobione."

    def _priority(self, snapshot: dict[str, Any]) -> str:
        return ProactiveDayAnalyzer.next_action(snapshot)

    def _completed_for(self, day: Any) -> list[dict[str, Any]]:
        expected = str(day)
        return [
            dict(item) for item in list(self._load().get("completed", []) or [])
            if str(item.get("day", "")) == expected
        ]

    def _actions_for(self, day: Any) -> list[str]:
        result: list[str] = []
        for item in list(self.context.load().get("history", []) or []):
            try:
                created = datetime.fromisoformat(str(item.get("created_at", "")))
                if created.astimezone().date() != day:
                    continue
            except (TypeError, ValueError):
                continue
            intent = str(item.get("intent", ""))
            labels = {
                "calendar_create": "dodano wydarzenie do kalendarza",
                "calendar_update": "zmieniono termin wydarzenia",
                "calendar_delete": "usunięto wydarzenie z kalendarza",
                "mail_draft": "przygotowano szkic wiadomości",
                "mail_send": "wysłano wiadomość",
                "mail_send_existing": "wysłano przygotowany szkic",
            }
            if intent in labels:
                result.append(labels[intent])
        return result

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        if not isinstance(value, dict):
            return self._default()
        data = self._default()
        data.update(value)
        return data

    @staticmethod
    def _safe(call: Callable[[], Any], fallback: Any) -> Any:
        try:
            return call()
        except Exception:
            return fallback

    @staticmethod
    def _title(event: dict[str, Any]) -> str:
        return DailyIntelligenceService._clean(event.get("title")) or "wydarzenie"

    @staticmethod
    def _mail_subject(message: dict[str, Any]) -> str:
        return (
            DailyIntelligenceService._clean(message.get("subject"))
            or "wiadomość wymagająca uwagi"
        )

    @staticmethod
    def _moment(value: object) -> str:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone().strftime("o %H:%M")
        except (TypeError, ValueError):
            return "w najbliższym terminie"

    @staticmethod
    def _clock(value: object) -> str:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%H:%M")
        except (TypeError, ValueError):
            return "bez godziny"

    @staticmethod
    def _clean(value: object) -> str:
        return IntelligentDayQuality.clean_text(value, 300)

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
