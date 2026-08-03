from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fold(value: object) -> str:
    text = str(value).casefold().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


class BrainContextV2:
    """B102 bounded contextual planner with explicit risk and clarification."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "intelligence" / "brain2.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.0",
            "turns": [],
            "last_plan": {},
            "updated_at": "",
        }

    def plan(self, command: object, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        text = " ".join(str(command).split()).strip()
        if not text:
            raise ValueError("Polecenie nie może być puste.")
        intent = self._intent(text)
        risk = self._risk(text, intent)
        clarification = self._clarification(text, intent)
        target = self._target(text)
        steps = self._steps(intent, target)
        plan = {
            "command": text,
            "intent": intent,
            "target": target,
            "risk": risk,
            "requires_confirmation": risk != "READ_ONLY",
            "clarification": clarification,
            "steps": steps,
            "context_keys": sorted(dict(context or {}).keys())[:20],
            "created_at": utc_now(),
        }
        data = self._load()
        turns = list(data.get("turns", []) or [])
        turns.append({
            "command": text,
            "intent": intent,
            "target": target,
            "risk": risk,
            "created_at": plan["created_at"],
        })
        data["turns"] = turns[-100:]
        data["last_plan"] = plan
        data["updated_at"] = utc_now()
        self.store.save(data)
        return plan

    def resolve_followup(self, command: object) -> str:
        text = " ".join(str(command).split()).strip()
        if fold(text) not in {"kontynuuj", "dalej", "jeszcze raz", "powtorz", "powtórz"}:
            return text
        last = dict(self._load().get("last_plan", {}) or {})
        return str(last.get("command") or text)

    def status(self) -> dict[str, Any]:
        data = self._load()
        turns = list(data.get("turns", []) or [])
        plan = dict(data.get("last_plan", {}) or {})
        return {
            "status": "BRAIN_2_READY",
            "turn_count": len(turns),
            "last_intent": plan.get("intent", ""),
            "last_target": plan.get("target", ""),
            "last_risk": plan.get("risk", ""),
            "last_steps": len(list(plan.get("steps", []) or [])),
            "clarification": plan.get("clarification", ""),
        }

    @staticmethod
    def _intent(text: str) -> str:
        value = fold(text)
        rules = (
            ("STATUS", ("status", "pokaż", "pokaz", "sprawdź", "sprawdz")),
            ("OPEN", ("otwórz", "otworz", "uruchom aplikację", "uruchom aplikacje")),
            ("SEARCH", ("wyszukaj", "znajdź", "znajdz", "poszukaj")),
            ("MEMORY", ("zapamiętaj", "zapamietaj", "przypomnij", "pamięć", "pamiec")),
            ("AUTOMATION", ("wykonaj", "zrób", "zrob", "automatycznie", "zadanie")),
            ("STOP", ("zatrzymaj", "anuluj", "przerwij")),
        )
        for intent, phrases in rules:
            if any(phrase in value for phrase in phrases):
                return intent
        return "GENERAL"

    @staticmethod
    def _risk(text: str, intent: str) -> str:
        value = fold(text)
        critical = ("usuń", "usun", "sformatuj", "wyślij", "wyslij", "kup", "zapłać", "zaplac")
        if any(word in value for word in critical):
            return "CRITICAL"
        if intent in {"STATUS", "SEARCH"}:
            return "READ_ONLY"
        if intent in {"OPEN", "MEMORY", "AUTOMATION", "STOP"}:
            return "CONTROLLED_WRITE"
        return "REVIEW"

    @staticmethod
    def _clarification(text: str, intent: str) -> str:
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        if len(words) <= 1 or fold(text) in {"zrób", "zrob", "otwórz", "otworz"}:
            return "Doprecyzuj obiekt albo oczekiwany rezultat polecenia."
        if intent == "GENERAL" and len(words) < 3:
            return "Doprecyzuj, co dokładnie JARVIS ma zrobić."
        return ""

    @staticmethod
    def _target(text: str) -> str:
        match = re.search(
            r"(?:status|otwórz|otworz|uruchom|wyszukaj|znajdź|znajdz|zapamiętaj|zapamietaj|zrób|zrob)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        return (match.group(1) if match else text).strip(" .,:;")[:300]

    @staticmethod
    def _steps(intent: str, target: str) -> list[str]:
        base = {
            "STATUS": ["Odczytać bieżący stan", "Sprawdzić spójność danych", "Przedstawić zwięzły wynik"],
            "OPEN": ["Rozpoznać aplikację lub zasób", "Sprawdzić warunki wykonania", "Otworzyć zasób", "Zweryfikować rezultat"],
            "SEARCH": ["Ustalić zakres wyszukiwania", "Wyszukać trafienia", "Uszeregować wyniki", "Przedstawić najważniejsze"],
            "MEMORY": ["Rozpoznać typ informacji", "Sprawdzić duplikaty", "Zapisać lokalnie", "Potwierdzić zapis"],
            "AUTOMATION": ["Rozbić cel na kroki", "Sprawdzić zależności i ryzyko", "Uruchomić jedno kontrolowane wykonanie", "Weryfikować każdy krok", "Zapisać raport"],
            "STOP": ["Znaleźć aktywne wykonanie", "Bezpiecznie zatrzymać", "Zwolnić dzierżawę", "Zapisać stan końcowy"],
            "GENERAL": ["Rozpoznać cel", "Dobrać właściwą usługę", "Sprawdzić bezpieczeństwo", "Przygotować odpowiedź"],
        }
        return [f"{step}: {target}" if index == 0 else step for index, step in enumerate(base[intent])]

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
