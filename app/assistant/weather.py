"""Fast, read-only weather answers backed by the public Open-Meteo API."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Callable

from app.assistant.natural_language import fold_text
from app.market_data.http_json import (
    JsonHttpTransport,
    MarketDataTransportError,
    PreparedJsonRequest,
)


class WeatherServiceError(RuntimeError):
    """A safe, user-facing weather lookup failure."""


@dataclass(frozen=True, slots=True)
class WeatherQuery:
    location: str
    day_offset: int = 0


@dataclass(frozen=True, slots=True)
class WeatherReport:
    location: str
    day_offset: int
    weather_code: int
    temperature: float | None
    apparent_temperature: float | None
    humidity: float | None
    wind_speed: float | None
    temperature_min: float
    temperature_max: float
    precipitation_probability: float | None


_WEATHER_DESCRIPTIONS = {
    0: "bezchmurnie",
    1: "przewa\u017cnie bezchmurnie",
    2: "cz\u0119\u015bciowe zachmurzenie",
    3: "pochmurno",
    45: "mg\u0142a",
    48: "mg\u0142a z osadzaj\u0105c\u0105 si\u0119 szadzi\u0105",
    51: "lekka m\u017cawka",
    53: "m\u017cawka",
    55: "silna m\u017cawka",
    56: "lekka marzn\u0105ca m\u017cawka",
    57: "silna marzn\u0105ca m\u017cawka",
    61: "lekki deszcz",
    63: "deszcz",
    65: "silny deszcz",
    66: "lekki marzn\u0105cy deszcz",
    67: "silny marzn\u0105cy deszcz",
    71: "lekkie opady \u015bniegu",
    73: "opady \u015bniegu",
    75: "silne opady \u015bniegu",
    77: "ziarna \u015bniegu",
    80: "lekkie przelotne opady",
    81: "przelotne opady",
    82: "gwa\u0142towne przelotne opady",
    85: "lekkie przelotne opady \u015bniegu",
    86: "silne przelotne opady \u015bniegu",
    95: "burza",
    96: "burza z lekkim gradem",
    99: "burza z silnym gradem",
}

_POLISH_LOCATION_ALIASES = {
    "bialymstoku": "bialystok",
    "bydgoszczy": "bydgoszcz",
    "gdansku": "gdansk",
    "gdyni": "gdynia",
    "gorzowie wielkopolskim": "gorzow wielkopolski",
    "katowicach": "katowice",
    "kielcach": "kielce",
    "krakowie": "krakow",
    "lublinie": "lublin",
    "lodzi": "lodz",
    "olsztynie": "olsztyn",
    "opolu": "opole",
    "poznaniu": "poznan",
    "rzeszowie": "rzeszow",
    "sopocie": "sopot",
    "szczecinie": "szczecin",
    "toruniu": "torun",
    "warszawie": "warszawa",
    "wroclawiu": "wroclaw",
    "zielonej gorze": "zielona gora",
}


class WeatherService:
    """Resolve a place and return current or next-day weather without a key."""

    geocoding_host = "geocoding-api.open-meteo.com"
    forecast_host = "api.open-meteo.com"

    def __init__(
        self,
        transport: Callable[[PreparedJsonRequest], Any] | None = None,
    ) -> None:
        self._transport = transport or JsonHttpTransport()

    @staticmethod
    def parse_command(command: object) -> WeatherQuery:
        text = " ".join(str(command or "").strip().split())
        folded = fold_text(text).strip(" .,!?:;")
        day_offset = 1 if re.search(r"\b(?:jutro|tomorrow)\b", folded) else 0
        patterns = (
            r"\bpogod\w*\s+(?:(?:jest|bedzie)\s+)?(?:(?:dzisiaj|dzis|teraz|jutro)\s+)?(?:w|dla)\s+(.+)$",
            r"\bweather\s+(?:(?:today|tomorrow)\s+)?(?:in|for)\s+(.+)$",
            r"\bpogoda\s+(.+)$",
            r"\bweather\s+(.+)$",
        )
        location = ""
        for pattern in patterns:
            match = re.search(pattern, folded)
            if match:
                location = match.group(1)
                break
        location = re.sub(
            r"\b(?:dzisiaj|dzis|teraz|jutro|today|tomorrow)\b$", "", location
        ).strip(" .,!?:;")
        if (
            not 2 <= len(location) <= 80
            or any(marker in location for marker in ("/", chr(92), "@", "#", "?", "="))
            or any(ord(char) < 32 for char in location)
        ):
            raise WeatherServiceError("missing_location")
        return WeatherQuery(location=location, day_offset=day_offset)

    def lookup(self, query: WeatherQuery) -> WeatherReport:
        geocoding_name = _POLISH_LOCATION_ALIASES.get(
            query.location, query.location
        )
        place_request = PreparedJsonRequest.build(
            host=self.geocoding_host,
            path="/v1/search",
            query=(
                ("name", geocoding_name),
                ("count", "1"),
                ("language", "pl"),
                ("format", "json"),
            ),
            timeout_seconds=5.0,
        )
        place_data = self._request(place_request)
        results = place_data.get("results") if isinstance(place_data, dict) else None
        if not isinstance(results, list) or not results:
            raise WeatherServiceError("location_not_found")
        place = results[0]
        if not isinstance(place, dict):
            raise WeatherServiceError("invalid_location_response")
        latitude = self._number(place.get("latitude"), minimum=-90, maximum=90)
        longitude = self._number(place.get("longitude"), minimum=-180, maximum=180)
        name = self._short_text(place.get("name"), 80)
        country = self._short_text(place.get("country"), 80, required=False)
        display_location = f"{name}, {country}" if country else name

        forecast_request = PreparedJsonRequest.build(
            host=self.forecast_host,
            path="/v1/forecast",
            query=(
                ("latitude", str(latitude)),
                ("longitude", str(longitude)),
                (
                    "current",
                    "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                ),
                (
                    "daily",
                    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                ),
                ("timezone", "auto"),
                ("forecast_days", "2"),
            ),
            timeout_seconds=5.0,
        )
        forecast = self._request(forecast_request)
        return self._report_from_response(display_location, query.day_offset, forecast)

    def format_for_command(self, command: object) -> str:
        try:
            query = self.parse_command(command)
            report = self.lookup(query)
        except WeatherServiceError as error:
            if str(error) == "missing_location":
                return (
                    "Podaj miasto, na przyk\u0142ad: "
                    "\u201eJaka jest pogoda w Warszawie?\u201d"
                )
            if str(error) == "location_not_found":
                return (
                    "Nie znalaz\u0142em tej miejscowo\u015bci. Podaj nazw\u0119 miasta, "
                    "a w razie potrzeby tak\u017ce kraj."
                )
            return "Nie mog\u0119 teraz pobra\u0107 pogody. Spr\u00f3buj ponownie za chwil\u0119."
        except MarketDataTransportError:
            return (
                "Nie mog\u0119 teraz pobra\u0107 pogody. Sprawd\u017a po\u0142\u0105czenie z internetem "
                "i spr\u00f3buj ponownie za chwil\u0119."
            )
        return self._format_report(report)

    def status(self) -> dict[str, object]:
        return {
            "status": "READY",
            "provider": "OPEN_METEO",
            "api_key_required": False,
            "read_only": True,
        }

    def _request(self, request: PreparedJsonRequest) -> Any:
        try:
            return self._transport(request)
        except MarketDataTransportError:
            raise
        except Exception as error:
            raise MarketDataTransportError("weather_response: unavailable") from error

    @classmethod
    def _report_from_response(
        cls,
        location: str,
        day_offset: int,
        response: object,
    ) -> WeatherReport:
        if not isinstance(response, dict):
            raise WeatherServiceError("invalid_forecast_response")
        daily = response.get("daily")
        if not isinstance(daily, dict):
            raise WeatherServiceError("invalid_forecast_response")
        daily_code = int(
            cls._daily_number(daily, "weather_code", day_offset, 0, 99)
        )
        low = cls._daily_number(daily, "temperature_2m_min", day_offset, -100, 70)
        high = cls._daily_number(daily, "temperature_2m_max", day_offset, -100, 70)
        precipitation = cls._daily_optional_number(
            daily, "precipitation_probability_max", day_offset, 0, 100
        )
        current = response.get("current") if day_offset == 0 else None
        if day_offset == 0 and not isinstance(current, dict):
            raise WeatherServiceError("invalid_forecast_response")
        code = (
            int(cls._number(current.get("weather_code"), minimum=0, maximum=99))
            if isinstance(current, dict)
            else daily_code
        )
        return WeatherReport(
            location=location,
            day_offset=day_offset,
            weather_code=code,
            temperature=(
                cls._number(
                    current.get("temperature_2m"), minimum=-100, maximum=70
                )
                if isinstance(current, dict)
                else None
            ),
            apparent_temperature=cls._optional_number(
                current.get("apparent_temperature") if isinstance(current, dict) else None,
                minimum=-120,
                maximum=90,
            ),
            humidity=cls._optional_number(
                current.get("relative_humidity_2m") if isinstance(current, dict) else None,
                minimum=0,
                maximum=100,
            ),
            wind_speed=cls._optional_number(
                current.get("wind_speed_10m") if isinstance(current, dict) else None,
                minimum=0,
                maximum=500,
            ),
            temperature_min=low,
            temperature_max=high,
            precipitation_probability=precipitation,
        )

    @classmethod
    def _format_report(cls, report: WeatherReport) -> str:
        condition = _WEATHER_DESCRIPTIONS.get(report.weather_code, "zmienne warunki")
        rain = (
            f", opady do {cls._format_number(report.precipitation_probability)}%"
            if report.precipitation_probability is not None
            else ""
        )
        range_text = (
            f"od {cls._format_number(report.temperature_min)}\u00b0C "
            f"do {cls._format_number(report.temperature_max)}\u00b0C"
        )
        if report.day_offset == 1:
            return (
                f"Jutro \u2014 {report.location}: {condition}, {range_text}{rain}. "
                "\u0179r\u00f3d\u0142o: Open-Meteo."
            )
        details = []
        if report.apparent_temperature is not None:
            details.append(
                f"odczuwalna {cls._format_number(report.apparent_temperature)}\u00b0C"
            )
        if report.humidity is not None:
            details.append(f"wilgotno\u015b\u0107 {cls._format_number(report.humidity)}%")
        if report.wind_speed is not None:
            details.append(f"wiatr {cls._format_number(report.wind_speed)} km/h")
        detail_text = ", ".join(details)
        if detail_text:
            detail_text = f" ({detail_text})"
        return (
            f"{report.location}: teraz {cls._format_number(report.temperature)}\u00b0C, "
            f"{condition}{detail_text}. Dzisiaj {range_text}{rain}. "
            "\u0179r\u00f3d\u0142o: Open-Meteo."
        )

    @staticmethod
    def _format_number(value: float | None) -> str:
        if value is None:
            return "brak danych"
        if math.isclose(value, round(value), abs_tol=0.05):
            return str(int(round(value)))
        return f"{value:.1f}".replace(".", ",")

    @classmethod
    def _daily_number(
        cls,
        data: dict[str, Any],
        key: str,
        index: int,
        minimum: float,
        maximum: float,
    ) -> float:
        values = data.get(key)
        if not isinstance(values, list) or len(values) <= index:
            raise WeatherServiceError("invalid_forecast_response")
        return cls._number(values[index], minimum=minimum, maximum=maximum)

    @classmethod
    def _daily_optional_number(
        cls,
        data: dict[str, Any],
        key: str,
        index: int,
        minimum: float,
        maximum: float,
    ) -> float | None:
        values = data.get(key)
        if not isinstance(values, list) or len(values) <= index:
            return None
        return cls._optional_number(values[index], minimum=minimum, maximum=maximum)

    @staticmethod
    def _number(value: object, *, minimum: float, maximum: float) -> float:
        try:
            selected = float(value)
        except (TypeError, ValueError) as error:
            raise WeatherServiceError("invalid_numeric_value") from error
        if not math.isfinite(selected) or not minimum <= selected <= maximum:
            raise WeatherServiceError("invalid_numeric_value")
        return selected

    @classmethod
    def _optional_number(
        cls,
        value: object,
        *,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if value is None:
            return None
        return cls._number(value, minimum=minimum, maximum=maximum)

    @staticmethod
    def _short_text(value: object, limit: int, *, required: bool = True) -> str:
        text = " ".join(str(value or "").split())
        if any(ord(char) < 32 for char in text) or len(text) > limit:
            raise WeatherServiceError("invalid_location_response")
        if required and not text:
            raise WeatherServiceError("invalid_location_response")
        return text


__all__ = [
    "WeatherQuery",
    "WeatherReport",
    "WeatherService",
    "WeatherServiceError",
]
