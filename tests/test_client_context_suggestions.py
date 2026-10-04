from __future__ import annotations

from datetime import datetime

from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_context_suggestions import context_suggestions
from app.natural_actions.understanding import NaturalActionUnderstanding


def _at(hour: int) -> datetime:
    return datetime(2026, 10, 4, hour, 0)


def test_suggestions_follow_the_part_of_day() -> None:
    morning, morning_actions = context_suggestions(_at(7))
    daytime, daytime_actions = context_suggestions(_at(13))
    evening, evening_actions = context_suggestions(_at(20))

    assert morning == "PORANEK"
    assert [item.label for item in morning_actions] == [
        "PLAN DNIA", "KALENDARZ", "POGODA",
    ]
    assert daytime == "DZIEŃ"
    assert [item.label for item in daytime_actions] == [
        "NAJWAŻNIEJSZE", "WAŻNA POCZTA", "PRZYPOMNIENIA",
    ]
    assert evening == "WIECZÓR"
    assert [item.label for item in evening_actions] == [
        "PODSUMUJ DZIEŃ", "UPORZĄDKUJ JUTRO", "PRZYPOMNIENIA",
    ]


def test_every_context_suggestion_is_real_and_client_safe() -> None:
    for hour in (7, 13, 20):
        _period, suggestions = context_suggestions(_at(hour))
        for suggestion in suggestions:
            assert ClientCapabilityPolicy.denial_message(suggestion.command) == ""
            natural, confidence = NaturalActionUnderstanding.classify(
                suggestion.command
            )
            core = NaturalLanguageService.classify(suggestion.command)
            assert natural != "standard" or core != "standard"
            if natural != "standard":
                assert confidence >= 0.7


def test_night_uses_calm_evening_suggestions() -> None:
    period, suggestions = context_suggestions(_at(2))

    assert period == "WIECZÓR"
    assert all("wyślij" not in item.command.casefold() for item in suggestions)
