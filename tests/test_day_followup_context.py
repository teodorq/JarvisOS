from __future__ import annotations

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.natural_actions.understanding import NaturalActionUnderstanding


class _NaturalDay:
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
        return f"Plan odczytany: {command}"


def test_day_followups_move_between_today_priority_and_tomorrow(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)
    language.context.update(
        command="Pokaż mój dzień", intent="day_overview", response="Plan dnia.",
    )

    priority = language.resolve("Co teraz?")
    assert priority.resolved == "Co powinienem zrobić teraz?"
    assert priority.used_context is True
    assert (
        language.resolve("A co najważniejsze?").resolved
        == "Co powinienem zrobić teraz?"
    )

    language.context.update(
        command=priority.resolved, intent="day_priority", response="Priorytet.",
    )
    tomorrow = language.resolve("A jutro?")
    assert tomorrow.resolved == "Uporządkuj mi jutro"

    language.context.update(
        command=tomorrow.resolved,
        intent="day_plan_tomorrow",
        response="Plan na jutro.",
    )
    today = language.resolve("A dzisiaj?")
    assert today.resolved == "Pokaż mój dzień"


def test_short_day_followup_without_day_context_is_not_guessed(tmp_path) -> None:
    resolved = NaturalLanguageService(tmp_path).resolve("Co teraz?")

    assert resolved.intent == "standard"
    assert resolved.used_context is False


def test_controller_remembers_each_exact_day_intent(tmp_path) -> None:
    controller = PersonalAssistantController(tmp_path)
    natural = _NaturalDay()
    controller.natural_actions = natural

    controller.handle("Pokaż mój dzień")
    controller.handle("Co teraz?")
    assert controller.conversation.context.load()["last_intent"] == "day_priority"

    controller.handle("A jutro?")
    assert controller.conversation.context.load()["last_intent"] == "day_plan_tomorrow"
    assert natural.commands[-1] == "Uporządkuj mi jutro"
