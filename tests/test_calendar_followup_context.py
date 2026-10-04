from __future__ import annotations

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.natural_actions.understanding import NaturalActionUnderstanding


class _NaturalCalendar:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.understanding = NaturalActionUnderstanding()

    @staticmethod
    def has_pending() -> bool:
        return False

    @staticmethod
    def matches(command: object) -> bool:
        intent, confidence = NaturalActionUnderstanding.classify(command)
        return intent != "standard" and confidence >= 0.7

    def handle(self, command: object) -> str:
        self.commands.append(str(command))
        return f"Kalendarz odczytany: {command}"


def test_calendar_followups_switch_the_period(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)
    language.context.update(
        command="Co mam dziś w kalendarzu?",
        intent="calendar_today_overview",
        response="Jedno wydarzenie.",
    )

    tomorrow = language.resolve("A jutro?")
    assert tomorrow.resolved == "Pokaż mój kalendarz na jutro"
    assert tomorrow.intent == "natural_action"
    assert tomorrow.used_context is True

    language.context.update(
        command=tomorrow.resolved,
        intent="calendar_tomorrow_overview",
        response="Dwa wydarzenia.",
    )
    week = language.resolve("A w tym tygodniu?")
    assert week.resolved == "Pokaż mój kalendarz na ten tydzień"

    language.context.update(
        command=week.resolved,
        intent="calendar_week_overview",
        response="Trzy wydarzenia.",
    )
    today = language.resolve("A dzisiaj?")
    assert today.resolved == "Pokaż mój kalendarz na dziś"


def test_short_followup_without_calendar_context_is_not_guessed(tmp_path) -> None:
    resolved = NaturalLanguageService(tmp_path).resolve("A jutro?")

    assert resolved.intent == "standard"
    assert resolved.used_context is False


def test_controller_remembers_exact_calendar_intent_between_turns(tmp_path) -> None:
    controller = PersonalAssistantController(tmp_path)
    natural = _NaturalCalendar()
    controller.natural_actions = natural

    controller.handle("Co mam dziś w kalendarzu?")
    assert controller.conversation.context.load()["last_intent"] == "calendar_today_overview"

    controller.handle("A jutro?")
    assert controller.conversation.context.load()["last_intent"] == "calendar_tomorrow_overview"
    assert natural.commands[-1] == "Pokaż mój kalendarz na jutro"
