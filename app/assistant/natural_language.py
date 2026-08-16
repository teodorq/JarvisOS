from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


_WAKE_WORDS = ("jarvis", "jarwis", "dżarwis", "dzarwis", "jervis")
_REPEAT_PHRASES = {
    "jeszcze raz",
    "powtórz",
    "powtorz",
    "powtórz to",
    "powtorz to",
    "zrób to jeszcze raz",
    "zrob to jeszcze raz",
}
_CONTINUE_PHRASES = {
    "kontynuuj",
    "dalej",
    "jedź dalej",
    "jedz dalej",
    "wróć do tego",
    "wroc do tego",
}
_POLITE_PREFIXES = (
    "proszę ",
    "prosze ",
    "czy możesz ",
    "czy mozesz ",
    "mógłbyś ",
    "moglbys ",
    "chciałbym żebyś ",
    "chcialbym zebys ",
    "hej ",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_POLISH_FOLD_TRANSLATION = str.maketrans({
    "ł": "l",
    "Ł": "l",
})


def fold_text(value: object) -> str:
    text = str(value).casefold().translate(_POLISH_FOLD_TRANSLATION)
    text = unicodedata.normalize("NFKD", text)
    return "".join(
        char for char in text
        if not unicodedata.combining(char)
    )


def normalize_user_command(value: object) -> str:
    text = " ".join(str(value).strip().split())
    lowered = text.casefold()
    for wake_word in _WAKE_WORDS:
        wake_match = re.match(
            rf"^{re.escape(wake_word)}(?:[\s,;:!?.-]+|$)",
            lowered,
        )
        if wake_match:
            if wake_match.end() >= len(text):
                return wake_word
            text = text[wake_match.end():].strip(" ,:-")
            lowered = text.casefold()
            break
    for prefix in _POLITE_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip()
            lowered = text.casefold()
            break
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class ResolvedCommand:
    original: str
    resolved: str
    intent: str
    used_context: bool = False
    clarification: str = ""


class ConversationContextStore:
    """B96 bounded local context for follow-ups and concise conversation."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "assistant" / "conversation_context.json"
        self.store = JsonStore(self.path, self._default)

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "last_command": "",
            "last_intent": "",
            "last_target": "",
            "active_topic": "",
            "turns": [],
            "updated_at": "",
        }

    def load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    def update(
        self,
        *,
        command: str,
        intent: str,
        target: str = "",
        response: str = "",
    ) -> None:
        data = self.load()
        data["last_command"] = command
        data["last_intent"] = intent
        if target:
            data["last_target"] = target
        data["updated_at"] = utc_now()
        turns = list(data.get("turns", []) or [])
        turns.append({
            "command": command,
            "intent": intent,
            "target": target,
            "response": response[:500],
            "created_at": data["updated_at"],
        })
        data["turns"] = turns[-50:]
        self.store.save(data)

    def set_topic(self, topic: str) -> None:
        data = self.load()
        data["active_topic"] = str(topic).strip()
        data["updated_at"] = utc_now()
        self.store.save(data)

    def clear(self) -> None:
        self.store.save(self._default())


class NaturalLanguageService:
    """Deterministic Polish command resolver with bounded conversation state."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.context = ConversationContextStore(project_root)

    def resolve(self, command: object) -> ResolvedCommand:
        original = str(command).strip()
        cleaned = normalize_user_command(original)
        folded = fold_text(cleaned)
        context = self.context.load()

        if folded in {fold_text(item) for item in _REPEAT_PHRASES}:
            previous = str(context.get("last_command", "")).strip()
            if previous:
                return ResolvedCommand(
                    original=original,
                    resolved=previous,
                    intent=str(context.get("last_intent", "repeat")) or "repeat",
                    used_context=True,
                )
            return ResolvedCommand(
                original=original,
                resolved=cleaned,
                intent="clarification",
                clarification="Nie mam jeszcze polecenia do powtórzenia.",
            )

        if folded in {fold_text(item) for item in _CONTINUE_PHRASES}:
            previous = str(context.get("last_command", "")).strip()
            if previous:
                return ResolvedCommand(
                    original=original,
                    resolved=previous,
                    intent="continue",
                    used_context=True,
                )

        last_target = str(context.get("last_target", "")).strip()
        temporal_determiner = bool(re.search(
            r"\b(?:ten|tego|te|to)\s+(?:tydzien|tygodnia|miesiac|miesiaca|rok|roku|kwartal|kwartalu|weekend|weekendu|dzien|dnia)\b",
            folded,
        ))
        if last_target and not temporal_determiner and re.search(r"\b(to|ten|tę|tego)\b", cleaned.casefold()):
            cleaned = re.sub(
                r"\b(to|ten|tę|tego)\b",
                last_target,
                cleaned,
                count=1,
                flags=re.IGNORECASE,
            )
            used_context = True
        else:
            used_context = False

        return ResolvedCommand(
            original=original,
            resolved=cleaned,
            intent=self.classify(cleaned),
            used_context=used_context,
        )

    @staticmethod
    def classify(command: object) -> str:
        text = fold_text(command)
        patterns = (
            ("clear_context", ("wyczysc kontekst rozmowy",)),
            ("capability_help", ("co potrafisz", "co umiesz", "co mozesz zrobic", "jakie masz funkcje", "pokaz pomoc", "pomoc jarvis", "jak z ciebie korzystac", "przyklady polecen", "lista polecen", "centrum mozliwosci")),
            ("current_time", ("ktora jest godzina", "jaka jest godzina", "podaj godzine", "powiedz mi godzine", "aktualna godzina")),
            ("integration_status", ("status integracji", "pokaz integracje", "jakie integracje", "polaczenia zewnetrzne", "status revenuecat", "status meta ads", "status claude", "status cartesia", "status elevenlabs")),
            ("assistant_status", ("status asystenta", "status b96", "status b100")),
            ("conversation_status", ("status rozmowy", "kontekst rozmowy")),
            ("memory_status", ("status pamieci projektow", "pamiec projektow")),
            ("voice_status", ("status glosu", "glos 2.0", "voice 2.0")),
            ("desktop_status", ("status sterowania pulpitem", "niezawodne sterowanie")),
            ("daily_status", ("centrum codziennej pracy", "status codziennej pracy")),
            ("remember_project", ("zapamietaj projekt", "dodaj projekt")),
            ("activate_project", ("ustaw aktywny projekt", "przelacz projekt")),
            ("remember_preference", ("zapamietaj preferencje", "ustaw preferencje")),
            ("add_workflow", ("utworz zadanie wieloetapowe", "dodaj workflow")),
            ("start_workflow", ("uruchom zadanie", "rozpocznij zadanie")),
            ("next_step", ("nastepny krok", "wykonano krok")),
            ("pause_workflow", ("wstrzymaj zadanie",)),
            ("resume_workflow", ("wznow zadanie",)),
            ("cancel_workflow", ("anuluj zadanie",)),
            ("reminder", ("dodaj przypomnienie", "przypomnij mi")),
        )
        for intent, phrases in patterns:
            if any(phrase in text for phrase in phrases):
                return intent
        return "standard"

    @staticmethod
    def extract_target(command: object) -> str:
        text = normalize_user_command(command)
        patterns = (
            r"(?:otwórz|otworz|uruchom|zamknij|aktywuj)\s+(.+)$",
            r"(?:projekt|stronę|strone|aplikację|aplikacje)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip(" .,:;")[:120]
        return ""
