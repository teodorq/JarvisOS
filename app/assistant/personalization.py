from __future__ import annotations

import re
from typing import Any

from app.assistant.natural_language import fold_text


class AssistantPersonalizationService:
    def __init__(self, projects: Any) -> None:
        self.projects = projects

    def remember_project(self, command: str) -> str:
        match = re.search(
            r"(?:zapamiętaj|zapamietaj|dodaj)\s+projekt\s+(.+?)(?:\s+w\s+([A-Za-z]:[\\/].+))?$",
            command,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("Użyj: Zapamiętaj projekt NAZWA w C:\\ścieżka.")
        project = self.projects.remember_project(
            match.group(1).strip(),
            path=(match.group(2) or "").strip(),
        )
        return f"B98: zapisano i aktywowano projekt „{project['name']}”."
    def activate_project(self, command: str) -> str:
        name = re.sub(
            r"^(?:ustaw aktywny projekt|przełącz projekt|przelacz projekt)\s*",
            "",
            command,
            flags=re.IGNORECASE,
        ).strip()
        project = self.projects.activate_project(name)
        return f"B98: aktywny projekt: {project['name']}."
    def remember_preference(self, command: str) -> str:
        content = re.sub(
            r"^(?:zapamiętaj|zapamietaj|ustaw)\s+preferencj(?:ę|e)\s*",
            "",
            command,
            flags=re.IGNORECASE,
        ).strip()
        if "=" in content:
            key, value = [part.strip() for part in content.split("=", 1)]
        elif ":" in content:
            key, value = [part.strip() for part in content.split(":", 1)]
        else:
            raise ValueError("Użyj: Zapamiętaj preferencję KLUCZ = WARTOŚĆ.")
        self.projects.set_preference(key, value)
        return f"B98: zapisano preferencję „{key}”."
    def set_conversation_style(self, command: str) -> str:
        text = fold_text(command)
        if any(value in text for value in ("krocej", "krotko", "krotki")):
            style, label = "concise", "krótki"
        elif any(value in text for value in ("dokladniej", "dokladny")):
            style, label = "detailed", "dokładny"
        elif any(value in text for value in ("luzniej", "luzny")):
            style, label = "casual", "luźny"
        elif any(value in text for value in ("naturalnie", "normalnie", "normalny")):
            style, label = "natural", "naturalny"
        else:
            raise ValueError(
                "Dostępne style rozmowy: krótki, dokładny, luźny i normalny."
            )
        self.projects.set_preference(
            "conversation_style", style, category="assistant_setting",
        )
        return f"Ustawiłem {label} styl rozmowy."
    def format_conversation_style(self) -> str:
        style = str(self.projects.get_preference("conversation_style", "natural"))
        labels = {
            "concise": "krótki",
            "detailed": "dokładny",
            "casual": "luźny",
            "natural": "naturalny",
            "neutral": "naturalny",
        }
        return f"Aktualny styl rozmowy: {labels.get(style, 'naturalny')}."
    @staticmethod
    def format_conversation_options() -> str:
        return (
            "Możemy rozmawiać swobodnie, omawiać pomysły, decyzje, emocje, "
            "plany, motywację i zapamiętane informacje. Style odpowiedzi: "
            "„mów krócej”, „mów dokładniej”, „rozmawiaj luźniej” albo "
            "„rozmawiaj naturalnie”. Domyślny tryb naturalny nie kończy "
            "odpowiedzi po kilku zdaniach, jeśli temat wymaga rozwinięcia. "
            "Pytania kontrolujesz poleceniami: „nie zadawaj mi pytań”, "
            "„pytaj naturalnie” albo „pytaj mnie częściej”."
        )
    def remember_personal_fact(self, command: str) -> str:
        match = re.match(
            r"^(?:zapamiętaj|zapamietaj|pamiętaj|pamietaj)(?:\s+sobie)?\s*,?\s*(?:że|ze)\s+(.+)$",
            command.strip(),
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("Powiedz na przykład: Zapamiętaj, że lubię kawę.")
        fact = " ".join(match.group(1).split()).strip(" .,:;")
        if self._looks_sensitive(fact):
            return (
                "Nie zapiszę hasła, tokenu, kodu PIN ani danych płatniczych. "
                "Takie informacje nie powinny trafiać do pamięci rozmowy."
            )
        saved = self.projects.remember_personal_fact(fact)
        return f"Zapamiętam: {saved.get('value', fact)}."
    def list_personal_memory(self) -> str:
        facts = self.projects.list_preferences(category="personal_fact", limit=10)
        if not facts:
            return "Nie mam jeszcze zapisanych informacji o Tobie."
        values = [str(item.get("value", "")).strip() for item in facts]
        return "Pamiętam:\n" + "\n".join(f"- {value}" for value in values if value)
    def forget_personal_fact(self, command: str) -> str:
        query = re.sub(
            r"^(?:zapomnij|usuń\s+z\s+pamięci|usun\s+z\s+pamieci)\s*"
            r"(?:o\s+tym\s*)?(?:informacj(?:ę|e)\s*)?(?:,?\s*(?:że|ze|o)\s*)?",
            "",
            command.strip(),
            flags=re.IGNORECASE,
        ).strip(" .,:;")
        if not query:
            raise ValueError("Powiedz dokładnie, którą informację mam zapomnieć.")
        matches = self.projects.find_personal_facts(query)
        if not matches:
            return "Nie znalazłem takiej informacji w pamięci."
        if len(matches) > 1:
            options = "; ".join(str(item.get("value", "")) for item in matches[:3])
            return f"Znalazłem kilka podobnych informacji: {options}. Powiedz dokładniej, którą usunąć."
        item = matches[0]
        self.projects.remove_preference(item.get("key", ""))
        return f"Zapomniałem: {item.get('value', query)}."
    @staticmethod
    def _looks_sensitive(value: object) -> bool:
        text = fold_text(value)
        markers = (
            "haslo", "password", "token", "kod pin", "pin to", "cvv",
            "numer karty", "klucz api", "api key", "sekret", "secret",
        )
        return any(marker in text for marker in markers)


__all__ = ["AssistantPersonalizationService"]
