from __future__ import annotations

import re


_STATUS_LABELS = {
    "ACTIVE": "AKTYWNA",
    "ATTENTION_REQUIRED": "WYMAGA UWAGI",
    "AVAILABLE": "DOSTĘPNE",
    "BASELINE_PENDING": "OCZEKUJE NA BASELINE",
    "CANARY": "KANAREK",
    "CHANGED": "WYKRYTO ZMIANY",
    "CLEAR": "CZYSTO",
    "CRITICAL": "KRYTYCZNY",
    "IDLE": "OCZEKUJE",
    "INTEGRITY_FAILED": "BŁĄD INTEGRALNOŚCI",
    "INVALID_MANIFEST": "BŁĘDNY MANIFEST",
    "LEASED": "DZIERŻAWA",
    "MONITOR": "MONITORUJ",
    "OFF": "WYŁĄCZONE",
    "ON": "WŁĄCZONE",
    "OWNER_DEVELOPMENT": "TRYB WŁAŚCICIELA",
    "PAUSED": "WSTRZYMANE",
    "READY": "GOTOWY",
    "REQUIRED": "WYMAGANE",
    "REVIEW": "SPRAWDŹ",
    "RUNNING": "AKTYWNE",
    "SAFETY_GATED": "ZABEZPIECZONE",
    "STARTING": "URUCHAMIANIE",
    "STOP": "ZATRZYMAJ",
    "STOPPED": "ZATRZYMANE",
    "UNKNOWN": "NIEZNANY",
    "VERIFIED": "ZWERYFIKOWANA",
}

_ENVIRONMENT_LABELS = {
    "OWNER_DEVELOPMENT": "ROZWÓJ WŁAŚCICIELSKI",
    "STAGING": "ŚRODOWISKO TESTOWE",
    "PRODUCTION": "PRODUKCJA",
    "DEMO": "DEMO",
}


def normalize_token(value: object) -> str:
    text = re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper())
    return text.strip("_")


def display_status(value: object, default: str = "NIEZNANY") -> str:
    token = normalize_token(value)
    if not token:
        return default
    return _STATUS_LABELS.get(token, token.replace("_", " "))


def display_environment(value: object) -> str:
    token = normalize_token(value)
    if not token:
        return "NIEUSTAWIONE"
    return _ENVIRONMENT_LABELS.get(token, token.replace("_", " "))


def same_identity(left: object, right: object) -> bool:
    return normalize_token(left) == normalize_token(right)


def compact_technical(value: object, limit: int = 54) -> str:
    text = str(value or "—")
    if len(text) <= limit:
        return text
    head = max(12, limit - 15)
    return f"{text[:head]}…{text[-10:]}"
