from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.assistant.conversation_context_policy import (
    FOLLOWUP_TTL,
    context_for_resolution,
)
from app.assistant.natural_language import NaturalLanguageService


def _age_context(service: NaturalLanguageService, age: timedelta) -> None:
    data = service.context.load()
    data["updated_at"] = (datetime.now(timezone.utc) - age).isoformat()
    service.context.store.save(data)


def test_recent_context_still_resolves_short_followups(tmp_path) -> None:
    service = NaturalLanguageService(tmp_path)
    service.context.update(
        command="Pokaż najnowsze maile Gmail",
        intent="gmail_search",
        response="Lista.",
    )

    assert service.resolve("Pierwszy").resolved == "Przeczytaj wiadomość numer 1"


def test_expired_context_does_not_open_an_old_mail_or_weather_target(tmp_path) -> None:
    service = NaturalLanguageService(tmp_path)
    service.context.update(
        command="Pokaż najnowsze maile Gmail",
        intent="gmail_search",
        response="Lista.",
    )
    _age_context(service, FOLLOWUP_TTL + timedelta(minutes=1))

    selected = service.resolve("Pierwszy")
    repeated = service.resolve("Jeszcze raz")

    assert selected.intent == "standard"
    assert selected.used_context is False
    assert repeated.intent == "clarification"
    assert "Nie mam jeszcze" in repeated.clarification


def test_expired_continue_is_a_clarification_not_a_status_command(tmp_path) -> None:
    service = NaturalLanguageService(tmp_path)
    service.context.update(
        command="Pokaż mój dzień", intent="day_overview", response="Plan.",
    )
    _age_context(service, timedelta(hours=2))

    resolved = service.resolve("Kontynuuj")

    assert resolved.intent == "clarification"
    assert "świeżego polecenia" in resolved.clarification


def test_expiry_hides_pointers_but_preserves_saved_history() -> None:
    now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    original = {
        "last_command": "Poufne polecenie",
        "last_intent": "gmail_read",
        "last_target": "wiadomość 1",
        "turns": [{"command": "Poufne polecenie"}],
        "updated_at": (now - timedelta(hours=2)).isoformat(),
    }

    resolved = context_for_resolution(original, now=now)

    assert resolved["last_command"] == ""
    assert resolved["last_intent"] == ""
    assert resolved["last_target"] == ""
    assert resolved["turns"] == original["turns"]
    assert original["last_command"] == "Poufne polecenie"
