from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs, urlsplit

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.assistant.weather import WeatherService, WeatherServiceError
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.market_data.http_json import MarketDataTransportError


class FakeWeatherTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def place_response() -> dict:
    return {
        "results": [
            {
                "name": "Miami",
                "country": "Stany Zjednoczone",
                "latitude": 25.774,
                "longitude": -80.194,
            }
        ]
    }


def forecast_response() -> dict:
    return {
        "current": {
            "temperature_2m": 29.2,
            "apparent_temperature": 33.1,
            "relative_humidity_2m": 72,
            "weather_code": 2,
            "wind_speed_10m": 18.4,
        },
        "daily": {
            "weather_code": [2, 61],
            "temperature_2m_max": [31.4, 30.1],
            "temperature_2m_min": [25.7, 24.9],
            "precipitation_probability_max": [40, 65],
        },
    }


class WeatherParsingTests(unittest.TestCase):
    def test_polish_current_and_tomorrow_commands(self) -> None:
        current = WeatherService.parse_command("Jaka jest pogoda w Miami?")
        tomorrow = WeatherService.parse_command(
            "Jaka bedzie pogoda jutro w Warszawie?"
        )
        self.assertEqual((current.location, current.day_offset), ("miami", 0))
        self.assertEqual((tomorrow.location, tomorrow.day_offset), ("warszawie", 1))

    def test_missing_or_url_location_is_rejected(self) -> None:
        for command in ("Jaka jest pogoda?", "pogoda w https://example.com"):
            with self.subTest(command=command):
                with self.assertRaises(WeatherServiceError):
                    WeatherService.parse_command(command)


class WeatherServiceTests(unittest.TestCase):
    def test_current_weather_uses_only_fixed_https_hosts(self) -> None:
        transport = FakeWeatherTransport([place_response(), forecast_response()])
        service = WeatherService(transport)

        text = service.format_for_command("Jaka jest pogoda w Miami?")

        self.assertIn("Miami, Stany Zjednoczone", text)
        self.assertIn("29,2\u00b0C", text)
        self.assertIn("cz\u0119\u015bciowe zachmurzenie", text)
        self.assertIn("\u0179r\u00f3d\u0142o: Open-Meteo", text)
        self.assertEqual(len(transport.requests), 2)
        geocoding, forecast = transport.requests
        self.assertEqual(urlsplit(geocoding.url).hostname, service.geocoding_host)
        self.assertEqual(urlsplit(forecast.url).hostname, service.forecast_host)
        self.assertEqual(parse_qs(urlsplit(geocoding.url).query)["name"], ["miami"])
        self.assertFalse(geocoding.public_summary()["has_credentials"])
        self.assertFalse(forecast.public_summary()["has_credentials"])

    def test_tomorrow_uses_daily_forecast_not_current_conditions(self) -> None:
        transport = FakeWeatherTransport([place_response(), forecast_response()])
        text = WeatherService(transport).format_for_command(
            "Jaka bedzie pogoda jutro w Miami?"
        )
        self.assertIn("Jutro \u2014 Miami", text)
        self.assertIn("lekki deszcz", text)
        self.assertIn("od 24,9\u00b0C do 30,1\u00b0C", text)
        self.assertIn("opady do 65%", text)
        self.assertNotIn("odczuwalna", text)

    def test_polish_locative_city_name_is_normalized_for_geocoding(self) -> None:
        transport = FakeWeatherTransport([place_response(), forecast_response()])
        WeatherService(transport).format_for_command(
            "Jaka bedzie pogoda jutro w Warszawie?"
        )
        query = parse_qs(urlsplit(transport.requests[0].url).query)
        self.assertEqual(query["name"], ["warszawa"])

    def test_current_condition_uses_current_not_daily_weather_code(self) -> None:
        forecast = forecast_response()
        forecast["current"]["weather_code"] = 3
        transport = FakeWeatherTransport([place_response(), forecast])
        text = WeatherService(transport).format_for_command("pogoda w Miami")
        self.assertIn("pochmurno", text)
        self.assertNotIn("cz\u0119\u015bciowe zachmurzenie", text)

    def test_network_and_unknown_location_fail_with_clear_message(self) -> None:
        offline = WeatherService(FakeWeatherTransport([
            MarketDataTransportError("unavailable")
        ]))
        unknown = WeatherService(FakeWeatherTransport([{"results": []}]))
        self.assertIn("po\u0142\u0105czenie z internetem", offline.format_for_command("pogoda w Miami"))
        self.assertIn("Nie znalaz\u0142em", unknown.format_for_command("pogoda w Atlantis"))

    def test_invalid_provider_numbers_fail_closed(self) -> None:
        broken = forecast_response()
        broken["current"]["temperature_2m"] = 900
        service = WeatherService(FakeWeatherTransport([place_response(), broken]))
        self.assertIn("Nie mog\u0119 teraz pobra\u0107 pogody", service.format_for_command("pogoda w Miami"))


class WeatherCommandIntegrationTests(unittest.TestCase):
    def test_weather_is_direct_read_only_and_client_safe(self) -> None:
        command = "Jaka jest pogoda w Miami?"
        self.assertEqual(NaturalLanguageService.classify(command), "weather")
        self.assertTrue(PersonalAssistantController.matches(command))
        self.assertEqual(ClientCapabilityPolicy.denial_message(command), "")
        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(Path(directory))
            thought = controller.plan(command)
        self.assertEqual(thought["assistant_intent"], "weather")
        self.assertTrue(thought["read_only"])
        self.assertEqual(thought["actions"], [])

    def test_controller_returns_weather_without_general_planner(self) -> None:
        transport = FakeWeatherTransport([place_response(), forecast_response()])
        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(Path(directory))
            controller.weather = WeatherService(transport)
            response = controller.handle("Jaka jest pogoda w Miami?")
        self.assertIn("Miami, Stany Zjednoczone", response)
        self.assertEqual(len(transport.requests), 2)


if __name__ == "__main__":
    unittest.main()
