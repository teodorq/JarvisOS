from __future__ import annotations

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.assistant.weather import WeatherService


class _Weather:
    parse_command = staticmethod(WeatherService.parse_command)

    @staticmethod
    def format_for_command(command: object) -> str:
        query = WeatherService.parse_command(command)
        return f"{query.location}|{query.day_offset}"

    @staticmethod
    def status() -> dict[str, object]:
        return {"status": "READY", "read_only": True}


def test_weather_followup_reuses_location_and_changes_day(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)
    language.context.update(
        command="Jaka jest pogoda w Warszawie?",
        intent="weather",
        target="warszawie",
        response="Słonecznie.",
    )

    tomorrow = language.resolve("A jutro?")
    today = language.resolve("A dzisiaj?")

    assert tomorrow.resolved == "Jaka jest pogoda jutro w warszawie?"
    assert tomorrow.intent == "weather"
    assert tomorrow.used_context is True
    assert WeatherService.parse_command(tomorrow.resolved).day_offset == 1
    assert today.resolved == "Jaka jest pogoda dzisiaj w warszawie?"
    assert WeatherService.parse_command(today.resolved).day_offset == 0


def test_weather_followup_can_change_only_the_location(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)
    language.context.update(
        command="Jaka będzie pogoda jutro w Warszawie?",
        intent="weather",
        target="warszawie",
        response="Słonecznie.",
    )

    resolved = language.resolve("A w Krakowie?")
    query = WeatherService.parse_command(resolved.resolved)

    assert resolved.used_context is True
    assert query.location == "krakowie"
    assert query.day_offset == 1


def test_short_followup_without_weather_context_is_not_guessed(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)

    resolved = language.resolve("A jutro?")

    assert resolved.intent == "standard"
    assert resolved.used_context is False


def test_real_controller_keeps_weather_context_between_turns(tmp_path) -> None:
    controller = PersonalAssistantController(tmp_path)
    controller.weather = _Weather()

    first = controller.handle("Jaka jest pogoda w Warszawie?")
    second = controller.handle("A jutro?")
    third = controller.handle("A w Krakowie?")

    assert first == "warszawie|0"
    assert second == "warszawie|1"
    assert third == "krakowie|1"
