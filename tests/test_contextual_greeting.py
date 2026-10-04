from __future__ import annotations

from datetime import datetime, timezone

from app.assistant.contextual_greeting import ContextualGreetingService
from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy


class _NaturalActions:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def handle(self, command: str) -> str:
        self.commands.append(command)
        return f"Wynik dla: {command}"


def _service(hour: int) -> tuple[ContextualGreetingService, _NaturalActions]:
    actions = _NaturalActions()
    service = ContextualGreetingService(
        actions,
        now_provider=lambda: datetime(2026, 10, 4, hour, tzinfo=timezone.utc),
    )
    return service, actions


def test_greeting_uses_a_useful_action_for_each_part_of_day() -> None:
    morning, morning_actions = _service(7)
    daytime, daytime_actions = _service(13)
    evening, evening_actions = _service(20)

    assert morning.reply().startswith("Dzień dobry.")
    assert morning_actions.commands == ["Pokaż mój plan na dziś"]
    assert daytime.reply().startswith("Cześć.")
    assert daytime_actions.commands == ["Co jest teraz najważniejsze?"]
    assert evening.reply().startswith("Dobry wieczór.")
    assert evening_actions.commands == ["Jak minął dzień?"]


def test_only_standalone_greetings_use_the_contextual_intent() -> None:
    for command in (
        "Dzień dobry",
        "Dzień dobry, Jarvis!",
        "Cześć",
        "Cześć Jarvis",
        "Dobry wieczór",
        "Witaj Jarvis",
    ):
        assert NaturalLanguageService.classify(command) == "contextual_greeting"
        assert PersonalAssistantController.matches(command) is True
        assert ClientCapabilityPolicy.denial_message(command) == ""

    assert NaturalLanguageService.classify(
        "Dzień dobry, dodaj spotkanie jutro"
    ) != "contextual_greeting"


def test_controller_plans_greeting_as_read_only_and_returns_context(tmp_path) -> None:
    controller = PersonalAssistantController(tmp_path)
    greeting, actions = _service(7)
    controller.greetings = greeting

    plan = controller.plan("Dzień dobry")
    response = controller.handle("Dzień dobry")

    assert plan["assistant_intent"] == "contextual_greeting"
    assert plan["read_only"] is True
    assert response == "Dzień dobry. Wynik dla: Pokaż mój plan na dziś"
    assert actions.commands == ["Pokaż mój plan na dziś"]
