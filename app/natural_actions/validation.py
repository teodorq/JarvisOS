from __future__ import annotations

from dataclasses import dataclass
import re

from app.assistant.natural_language import fold_text


_EMAIL = re.compile(r"^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$")
_PLACEHOLDER_MARKERS = {
    "imie lub adres",
    "imię lub adres",
    "adres email",
    "adres e-mail",
    "email",
    "e-mail",
    "odbiorca",
    "ktos",
    "ktoś",
    "example@example.com",
    "adres@example.com",
}
_ACCEPTED = {
    "tak",
    "ta",
    "jasne",
    "dobrze",
    "zgoda",
    "wykonaj",
    "potwierdzam",
    "potwierdz",
    "ok",
    "okej",
    "mozesz",
    "możesz",
}
_REJECTED = {
    "nie",
    "anuluj",
    "odwolaj",
    "odwołaj",
    "stop",
    "niewazne",
    "nieważne",
    "zrezygnuj",
}


@dataclass(frozen=True, slots=True)
class ConfirmationDecision:
    kind: str
    text: str


def clean_reference(value: object) -> str:
    return " ".join(str(value or "").split()).strip(" ,.;:'\"„”")


def is_placeholder(value: object) -> bool:
    raw = clean_reference(value)
    if not raw:
        return True
    folded = fold_text(raw).strip("[](){}<> ")
    if any(marker in folded for marker in {fold_text(item) for item in _PLACEHOLDER_MARKERS}):
        return True
    return bool(re.search(r"[\[\]{}<>]", raw))


def valid_email(value: object) -> bool:
    return bool(_EMAIL.fullmatch(clean_reference(value)))


def classify_confirmation(value: object) -> ConfirmationDecision:
    text = clean_reference(value)
    folded = fold_text(text)
    compact = re.sub(r"[^a-z0-9ąćęłńóśźż ]+", " ", folded)
    compact = " ".join(compact.split())
    if compact in {fold_text(item) for item in _ACCEPTED}:
        return ConfirmationDecision("accept", text)
    if compact in {fold_text(item) for item in _REJECTED}:
        return ConfirmationDecision("reject", text)
    if not compact:
        return ConfirmationDecision("unknown", text)
    return ConfirmationDecision("revise", text)
