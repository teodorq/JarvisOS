from __future__ import annotations

import re
import unicodedata


def resolve_contextual_followup(
    command: str,
    *,
    last_command: str,
    last_intent: str,
    last_target: str,
) -> tuple[str, str]:
    """Resolve only short follow-ups whose previous topic is unambiguous."""
    folded = _fold(command).strip(" .,!?:;")
    resolved = _weather_followup(
        folded, last_command=last_command, last_intent=last_intent,
        last_target=last_target,
    )
    if resolved:
        return resolved, "weather"
    resolved = _calendar_followup(folded, last_intent=last_intent)
    if resolved:
        return resolved, "natural_action"
    resolved = _day_followup(folded, last_intent=last_intent)
    return (resolved, "natural_action") if resolved else ("", "")


def _weather_followup(
    folded: str, *, last_command: str, last_intent: str, last_target: str,
) -> str:
    if last_intent != "weather" or not last_target:
        return ""
    if folded in {"a jutro", "jutro", "a dzisiaj", "a dzis", "dzisiaj", "dzis"}:
        day = "jutro" if "jutro" in folded else "dzisiaj"
        return f"Jaka jest pogoda {day} w {last_target}?"
    location = re.fullmatch(r"(?:a\s+)?w\s+([\w\s-]{2,80})", folded)
    if location:
        day = "jutro" if "jutro" in _fold(last_command) else "dzisiaj"
        return f"Jaka jest pogoda {day} w {location.group(1).strip()}?"
    return ""


def _calendar_followup(folded: str, *, last_intent: str) -> str:
    if last_intent not in {
        "calendar_today_overview", "calendar_tomorrow_overview",
        "calendar_week_overview",
    }:
        return ""
    if folded in {"a jutro", "jutro"}:
        return "Pokaż mój kalendarz na jutro"
    if folded in {"a dzisiaj", "a dzis", "dzisiaj", "dzis"}:
        return "Pokaż mój kalendarz na dziś"
    if folded in {
        "a ten tydzien", "ten tydzien", "a w tym tygodniu", "w tym tygodniu",
    }:
        return "Pokaż mój kalendarz na ten tydzień"
    return ""


def _day_followup(folded: str, *, last_intent: str) -> str:
    day_intents = {
        "day_overview", "day_review", "day_business_summary", "day_priority",
        "day_plan_tomorrow",
    }
    if last_intent not in day_intents:
        return ""
    if folded in {
        "a co teraz", "co teraz", "a co dalej", "co dalej",
        "a co jest najwazniejsze", "a co najwazniejsze",
        "co najwazniejsze", "a najwazniejsze",
    }:
        return "Co powinienem zrobić teraz?"
    if folded in {"a jutro", "jutro", "a plan na jutro", "plan na jutro"}:
        return "Uporządkuj mi jutro"
    if last_intent == "day_plan_tomorrow" and folded in {
        "a dzisiaj", "a dzis", "dzisiaj", "dzis",
    }:
        return "Pokaż mój dzień"
    return ""


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold().replace("ł", "l"))
    return "".join(char for char in text if not unicodedata.combining(char))


__all__ = ["resolve_contextual_followup"]
