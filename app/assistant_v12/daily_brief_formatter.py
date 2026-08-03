from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class DailyBriefFormatter:
    """Turns productivity counters into a short, useful client briefing."""

    @classmethod
    def format(cls, snapshot: dict[str, Any]) -> str:
        mail = dict(snapshot.get("mail", {}) or {})
        calendar = dict(snapshot.get("calendar", {}) or {})
        reminders = dict(snapshot.get("reminders", {}) or {})

        draft_count = cls._count(mail.get("draft_count"))
        high_priority = cls._count(mail.get("high_priority_count"))
        upcoming_count = cls._count(calendar.get("upcoming_count"))
        pending_count = cls._count(reminders.get("pending_count"))
        due_count = cls._count(reminders.get("due_count"))

        next_event = dict(calendar.get("next_event", {}) or {})
        next_reminder = dict(reminders.get("next_reminder", {}) or {})
        event_title = cls._clean(next_event.get("title"))
        reminder_text = cls._clean(next_reminder.get("text"))

        details: list[str] = []
        priority = cls._priority_sentence(
            due_count=due_count,
            reminder_text=reminder_text,
            reminder_due=next_reminder.get("due_at"),
            event_title=event_title,
            event_start=next_event.get("start_at"),
            high_priority=high_priority,
        )

        if priority:
            details.append(priority)

        if upcoming_count == 0:
            details.append("Nie masz zaplanowanych spotkań.")
        elif event_title and not priority.startswith("Najbliższe spotkanie"):
            moment = cls._human_time(next_event.get("start_at"))
            details.append(
                f"Najbliższe spotkanie: „{event_title}”{moment}."
            )
        elif not event_title:
            details.append(
                f"Masz {cls._plural(upcoming_count, 'spotkanie', 'spotkania', 'spotkań')}."
            )

        if pending_count and not reminder_text:
            details.append(
                f"Masz {cls._plural(pending_count, 'oczekujące przypomnienie', 'oczekujące przypomnienia', 'oczekujących przypomnień')}."
            )
        elif reminder_text and not priority.startswith(
            ("Najważniejsze teraz", "Najbliższe przypomnienie")
        ):
            moment = cls._human_time(next_reminder.get("due_at"))
            details.append(
                f"Najbliższe przypomnienie: „{reminder_text}”{moment}."
            )

        if draft_count:
            noun = cls._plural(draft_count, "szkic", "szkice", "szkiców")
            details.append(f"W poczcie czeka {noun}.")

        if not priority and upcoming_count == 0 and pending_count == 0 and draft_count == 0:
            return (
                "Twój dzień jest spokojny — nie masz zaplanowanych spotkań "
                "ani oczekujących przypomnień. Możesz wybrać najważniejszy cel."
            )

        return "Twój dzień: " + " ".join(details)

    @classmethod
    def _priority_sentence(
        cls,
        *,
        due_count: int,
        reminder_text: str,
        reminder_due: object,
        event_title: str,
        event_start: object,
        high_priority: int,
    ) -> str:
        if due_count and reminder_text:
            moment = cls._human_time(reminder_due)
            return f"Najważniejsze teraz: „{reminder_text}”{moment}."
        if event_title:
            moment = cls._human_time(event_start)
            return f"Najbliższe spotkanie: „{event_title}”{moment}."
        if reminder_text:
            moment = cls._human_time(reminder_due)
            return f"Najbliższe przypomnienie: „{reminder_text}”{moment}."
        if high_priority:
            noun = cls._plural(
                high_priority,
                "ważny szkic",
                "ważne szkice",
                "ważnych szkiców",
            )
            return f"Najważniejsze: w poczcie czeka {noun}."
        return ""

    @staticmethod
    def _human_time(value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            local = parsed.astimezone()
        except (TypeError, ValueError, OSError):
            return ""
        today = datetime.now().astimezone().date()
        if local.date() == today:
            return f" dzisiaj o {local:%H:%M}"
        if local.date() == today + timedelta(days=1):
            return f" jutro o {local:%H:%M}"
        return f" {local:%d.%m} o {local:%H:%M}"

    @staticmethod
    def _plural(count: int, one: str, few: str, many: str) -> str:
        value = max(0, int(count))
        if value == 1:
            word = one
        elif value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
            word = few
        else:
            word = many
        return f"{value} {word}"

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _clean(value: object) -> str:
        return " ".join(str(value or "").split()).strip()
