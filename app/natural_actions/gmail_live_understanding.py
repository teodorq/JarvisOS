from __future__ import annotations

import re
from typing import Any

from app.assistant.natural_language import fold_text


GMAIL_LIVE_INTENTS = {
    "gmail_search", "gmail_read", "gmail_thread", "gmail_reply_draft",
}
_READ_VERBS = r"(?:pokaz|przeczytaj|otworz|wyswietl|podsumuj)"
_REPLY_VERBS = r"(?:odpisz|odpowiedz|przygotuj|napisz|utworz|stworz|zredaguj)"


def classify_gmail_live(text: str) -> tuple[str, float] | None:
    folded = fold_text(text)
    gmail_signal = any(word in folded for word in (
        "mail", "email", "e-mail", "wiadomosc", "poczta", "gmail", "watek",
    ))
    reply_signal = bool(re.search(
        rf"\b{_REPLY_VERBS}\b.*\b(?:odpowiedz|odpis|reply|szkic)\w*\b", folded,
    )) or bool(re.match(r"^(?:odpisz|odpowiedz)\b", folded))
    if reply_signal:
        return "gmail_reply_draft", 0.99
    search_signal = bool(re.search(
        r"\b(?:znajdz|wyszukaj|poszukaj|najnowsz\w*|ostatni\w*|"
        r"maile|wiadomosci|skrzynk\w*)\b", folded,
    ))
    if gmail_signal and search_signal:
        return "gmail_search", 0.97
    if re.search(rf"\b{_READ_VERBS}\b.*\b(?:caly\s+)?watek\b", folded):
        return "gmail_thread", 0.99
    if re.search(
        rf"\b{_READ_VERBS}\b.*\b(?:mail|email|wiadomosc|tresc)\w*\b", folded,
    ):
        return "gmail_read", 0.98
    return None


def extract_gmail_live_slots(
    intent: str, text: str, existing: dict[str, Any]
) -> dict[str, Any]:
    slots = dict(existing)
    folded = fold_text(text)
    if intent == "gmail_search":
        email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        sender = _capture(text, r"\bod\s+(.+?)(?=\s+(?:o|z\s+tematem|dotycz)|$)")
        subject = _capture(text, r"\b(?:o|z\s+tematem|dotycz[aą]c[ey])\s+(.+)$")
        if email:
            query = f"in:anywhere from:{email.group(0)}"
        elif sender:
            query = f'in:anywhere from:"{sender}"'
        elif subject:
            query = f'in:anywhere subject:"{subject}"'
        elif any(word in folded for word in ("najnowsz", "ostatni", "skrzynk")):
            query = "in:inbox"
        else:
            remainder = re.sub(
                r"(?i)\b(?:znajdź|znajdz|wyszukaj|poszukaj|pokaż|pokaz)\b", "", text,
            )
            remainder = re.sub(
                r"(?i)\b(?:maile?|e-?maile?|wiadomości|wiadomosci|gmail)\b", "", remainder,
            )
            query = " ".join(remainder.split()).strip(" ,.-") or "in:inbox"
        slots.update({
            "query": query[:500],
            "select_first": bool(re.search(r"\b(?:ostatni\w*|najnowsz\w*)\b", folded)),
        })
    elif intent in {"gmail_read", "gmail_thread"}:
        index = re.search(r"\b(\d{1,2})\b", folded)
        ordinal = {
            "pierwszy": "1", "pierwsza": "1", "pierwsza wiadomosc": "1",
            "drugi": "2", "druga": "2", "trzeci": "3", "trzecia": "3",
        }
        slots["message_ref"] = index.group(1) if index else next(
            (number for word, number in ordinal.items() if word in folded), ""
        )
        slots["include_full_message"] = intent == "gmail_thread" and bool(
            re.search(r"\b(?:mail|email|wiadomosc|tresc)\w*\b", folded)
        )
    elif intent == "gmail_reply_draft":
        body = _reply_body(text)
        if body:
            slots["body"] = body
    return slots


def _reply_body(text: str) -> str:
    patterns = (
        r"\b(?:że|ze|tre[sś][cć])\s*[:,-]?\s*(.+)$",
        r"\b(?:przygotuj|napisz|utw[oó]rz|stw[oó]rz|zredaguj)\s+"
        r"(?:szkic\s+)?odpowied(?:ź|z|zi)\b(?:\s+na\s+.+?)?\s*[:,-]\s*(.+)$",
        r"\b(?:odpisz|odpowiedz)\b(?:\s+na\s+.+?)?\s*[:,-]\s*(.+)$",
    )
    for pattern in patterns:
        value = _capture(text, pattern)
        if value:
            return value[:10_000]
    return ""


def _capture(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.I)
    return " ".join(match.group(1).split()).strip(" ,.-") if match else ""
