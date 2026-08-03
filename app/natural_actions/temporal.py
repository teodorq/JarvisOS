from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from typing import Callable

from app.assistant.natural_language import fold_text


_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "wrzesnia": 9, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}
_WEEKDAYS = {
    "poniedzialek": 0, "wtorek": 1, "srode": 2, "sroda": 2,
    "czwartek": 3, "piatek": 4, "sobote": 5, "sobota": 5,
    "niedziele": 6, "niedziela": 6,
}
_DAYPARTS = {"rano": 9, "poludnie": 12, "popoludniu": 15, "wieczorem": 18}
_HOUR_WORDS = {
    "pierwszej": 1, "drugiej": 2, "trzeciej": 3, "czwartej": 4,
    "piatej": 5, "szostej": 6, "siodmej": 7, "osmej": 8,
    "dziewiatej": 9, "dziesiatej": 10, "jedenastej": 11,
    "dwunastej": 12, "trzynastej": 13, "czternastej": 14,
    "pietnastej": 15, "szesnastej": 16, "siedemnastej": 17,
    "osiemnastej": 18, "dziewietnastej": 19, "dwudziestej": 20,
    "dwudziestej pierwszej": 21, "dwudziestej drugiej": 22,
    "dwudziestej trzeciej": 23,
}
_NUMBER_WORDS = {
    "jeden": 1, "jedna": 1, "jedno": 1, "dwie": 2, "dwa": 2,
    "trzy": 3, "cztery": 4, "piec": 5, "szesc": 6, "siedem": 7,
    "osiem": 8, "dziewiec": 9, "dziesiec": 10, "jedenascie": 11,
    "dwanascie": 12, "trzynascie": 13, "czternascie": 14,
    "pietnascie": 15, "szesnascie": 16, "siedemnascie": 17,
    "osiemnascie": 18, "dziewietnascie": 19, "dwadziescia": 20,
    "trzydziesci": 30, "czterdziesci": 40, "piecdziesiat": 50,
    "szescdziesiat": 60,
}


class PolishTemporalParser:
    """Flexible Polish date, time, duration and reminder extraction."""

    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self.now_provider = now_provider or (lambda: datetime.now().astimezone())

    def parse_when(self, text: str) -> datetime | None:
        now = self.now_provider().astimezone()
        folded = fold_text(text)
        relative = self._relative(folded, now)
        if relative is not None:
            return relative
        target_date = self.parse_date(text, today=now.date())
        target_time = self.parse_time(text)
        if target_date is None and target_time is None:
            return None
        if target_date is None:
            target_date = now.date()
        if target_time is None:
            return None
        result = datetime.combine(target_date, target_time, tzinfo=now.tzinfo)
        if result <= now and not self._explicit_day(folded):
            result += timedelta(days=1)
        return result

    def parse_date(self, text: str, *, today: date | None = None) -> date | None:
        current = today or self.now_provider().astimezone().date()
        return self._date(text, fold_text(text), current)

    def parse_time(self, text: str) -> time | None:
        return self._time(text, fold_text(text))

    def duration_minutes(self, text: str, *, default: int = 60) -> int:
        folded = fold_text(text)
        match = re.search(
            r"\b(?:na|przez)\s+(\d{1,3})\s*(min(?:ut(?:y|e)?)?|godz(?:in(?:y|e)?)?)\b",
            folded,
        )
        if match:
            value = int(match.group(1))
            return max(5, min(value * (60 if match.group(2).startswith("godz") else 1), 1440))
        words = re.search(
            r"\b(?:na|przez)\s+([a-z ]{2,24})\s+(minut\w*|godzin\w*)\b",
            folded,
        )
        if words:
            value = self._word_number(words.group(1))
            if value is not None:
                return max(5, min(value * (60 if words.group(2).startswith("godzin") else 1), 1440))
        if re.search(r"\b(?:na|przez)\s+(?:pol|pół)\s+godziny\b", text, re.I):
            return 30
        if re.search(r"\b(?:na|przez)\s+godzine\b", folded):
            return 60
        return max(5, min(int(default), 1440))

    def reminder_minutes(self, text: str) -> int | None:
        folded = fold_text(text)
        patterns = (
            (r"(\d{1,4})\s*min(?:ut(?:y|e)?)?\s*(?:przed|wczesniej)", 1),
            (r"(\d{1,3})\s*godz(?:in(?:y|e)?)?\s*(?:przed|wczesniej)", 60),
            (r"(\d{1,3})\s*dni?\s*(?:przed|wczesniej)", 1440),
        )
        for pattern, multiplier in patterns:
            match = re.search(pattern, folded)
            if match:
                return min(int(match.group(1)) * multiplier, 40320)
        word_matches = re.finditer(
            r"(?=\b([a-z]+(?:\s+[a-z]+)?)\s+"
            r"(minut\w*|godzin\w*|dni?)\s*(?:przed|wczesniej)\b)",
            folded,
        )
        for words in word_matches:
            value = self._word_number(words.group(1))
            if value is None:
                continue
            unit = words.group(2)
            multiplier = (
                60 if unit.startswith("godzin")
                else 1440 if unit.startswith("dni")
                else 1
            )
            return min(value * multiplier, 40320)
        if re.search(r"\bpol\s+godziny\s+(?:przed|wczesniej)\b", folded):
            return 30
        if re.search(r"\bgodzine\s+(?:przed|wczesniej)\b", folded):
            return 60
        if "przypomnij" in folded and any(word in folded for word in ("przed", "wczesniej")):
            return 15
        return None

    def strip_temporal(self, text: str) -> str:
        patterns = (
            r"\b(?:dzisiaj|dziś|jutro|pojutrze)\b",
            r"\b(?:w\s+)?(?:poniedziałek|wtorek|środę|środa|czwartek|piątek|sobotę|sobota|niedzielę|niedziela)\b",
            r"\b(?:na|przez)\s+(?:\d+|pół|pol|[A-Za-ząćęłńóśźż]+(?:\s+[A-Za-ząćęłńóśźż]+)?)?\s*(?:minut\w*|godzin\w*|godzine)\b",
            # Match the full ISO date before shorter numeric forms.
            # Otherwise ``2026-07-28`` can be reduced to the orphaned year
            # ``2026`` when the shorter pattern consumes only ``07-28``.
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
            r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b",
            r"\b(?:o|na)\s*\d{1,2}(?::\d{2})?\b",
            r"\bo\s+(?:pierwszej|drugiej|trzeciej|czwartej|piątej|szóstej|siódmej|ósmej|dziewiątej|dziesiątej|jedenastej|dwunastej|trzynastej|czternastej|piętnastej|szesnastej|siedemnastej|osiemnastej|dziewiętnastej|dwudziestej(?:\s+(?:pierwszej|drugiej|trzeciej))?)\b",
            r"\bo\s+tej\s+samej\s+porze\b",
            r"\b\d{1,2}:\d{2}\b",
            r"\b(?:rano|w południe|popołudniu|wieczorem)\b",
            r"\b(?:i\s+)?przypomnij.*$",
        )
        result = text
        for pattern in patterns:
            result = re.sub(pattern, " ", result, flags=re.I)
        return " ".join(result.split()).strip(" ,.-")

    @staticmethod
    def _relative(folded: str, now: datetime) -> datetime | None:
        match = re.search(r"\bza\s+(\d{1,4})\s*(min|minut\w*|godz\w*|dni?|dzien)\b", folded)
        if not match:
            return None
        value = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("min"):
            return now + timedelta(minutes=value)
        if unit.startswith("godz"):
            return now + timedelta(hours=value)
        return now + timedelta(days=value)

    def _date(self, text: str, folded: str, today: date) -> date | None:
        if "pojutrze" in folded:
            return today + timedelta(days=2)
        if "jutro" in folded:
            return today + timedelta(days=1)
        if "dzisiaj" in folded or "dzis" in folded:
            return today
        iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
        if iso:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        numeric = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", text)
        if numeric:
            year = int(numeric.group(3) or today.year)
            year += 2000 if year < 100 else 0
            result = date(year, int(numeric.group(2)), int(numeric.group(1)))
            return result.replace(year=result.year + 1) if result < today and not numeric.group(3) else result
        named = re.search(r"\b(\d{1,2})\s+([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)(?:\s+(\d{4}))?\b", text)
        if named:
            month = _MONTHS.get(fold_text(named.group(2)))
            if month:
                year = int(named.group(3) or today.year)
                result = date(year, month, int(named.group(1)))
                return result.replace(year=year + 1) if result < today and not named.group(3) else result
        for name, weekday in _WEEKDAYS.items():
            if re.search(rf"\b{name}\b", folded):
                delta = (weekday - today.weekday()) % 7
                return today + timedelta(days=delta or 7)
        return None

    @staticmethod
    def _time(text: str, folded: str) -> time | None:
        matches = list(re.finditer(
            r"\bo\s*([01]?\d|2[0-3])(?:[:.]([0-5]\d))?\b",
            text,
            re.I,
        ))
        if not matches:
            matches = list(re.finditer(
                r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
                text,
            ))
        if not matches:
            matches = list(re.finditer(
                r"\bna\s*([01]?\d|2[0-3])(?::([0-5]\d))?\b",
                text,
                re.I,
            ))
        if matches:
            match = matches[-1]
            return time(int(match.group(1)), int(match.group(2) or 0))
        for phrase, hour in sorted(
            _HOUR_WORDS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(rf"\bo\s+{re.escape(phrase)}\b", folded):
                return time(hour, 0)
        for name, hour in _DAYPARTS.items():
            if name in folded:
                return time(hour, 0)
        return None

    @staticmethod
    def _word_number(value: str) -> int | None:
        words = [word for word in fold_text(value).split() if word]
        if not words:
            return None
        direct = _NUMBER_WORDS.get(" ".join(words))
        if direct is not None:
            return direct
        total = 0
        for word in words:
            number = _NUMBER_WORDS.get(word)
            if number is None:
                return None
            total += number
        return total if 0 < total <= 1440 else None

    @staticmethod
    def _explicit_day(folded: str) -> bool:
        return any(token in folded for token in ("dzis", "jutro", "pojutrze")) or any(
            re.search(rf"\b{name}\b", folded) for name in _WEEKDAYS
        )
