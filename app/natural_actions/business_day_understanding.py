from __future__ import annotations

from app.assistant.natural_language import fold_text


BUSINESS_DAY_INTENTS = {
    "day_overview",
    "day_review",
    "day_business_summary",
    "calendar_today_overview",
    "calendar_week_overview",
    "documents_recent",
    "reminders_overview",
    "bills_overview",
    "advertising_overview",
    "trading_overview",
}


def classify_business_day(text: str) -> tuple[str, float] | None:
    value = fold_text(text)
    if any(phrase in value for phrase in (
        "jaki jest moj plan dnia", "jaki mam plan dnia",
        "jakie mam plany na dzis", "jakie mam plany na dzisiaj",
        "pokaz moj plan dnia", "pokaz plan dnia",
        "co mam dzis do zrobienia", "co mam dzisiaj do zrobienia",
    )):
        return "day_overview", 0.99
    if any(phrase in value for phrase in (
        "jak minal dzien", "jak mi minal dzien", "jak nam minal dzien",
        "jak poszedl dzien", "podsumuj moj dzien", "podsumuj mi dzien",
    )):
        return "day_review", 0.99
    if any(phrase in value for phrase in (
        "podsumuj biznes", "podsumowanie biznesu", "wynik biznesu",
        "wynik dnia firmy", "ile dzis zarobilismy", "ile zarobilismy dzis",
        "podsumowanie firmy", "jak poszedl biznes",
    )):
        return "day_business_summary", 0.99
    if "kalendar" in value and any(phrase in value for phrase in (
        "ten tydzien", "tym tygodniu", "kalendarz tygodnia",
        "najblizsze 7 dni", "najblizszych 7 dni",
    )):
        return "calendar_week_overview", 0.99
    if "kalendar" in value and any(phrase in value for phrase in (
        "co mam dzis", "co mam dzisiaj", "kalendarz na dzis",
        "dzisiejszy kalendarz", "pokaz kalendarz", "otworz kalendarz",
        "plan w kalendarzu",
    )):
        return "calendar_today_overview", 0.99
    if any(phrase in value for phrase in (
        "ostatnio uzywany dokument", "ostatnie dokumenty",
        "ostatni dokument", "pokaz dokumenty", "co mam w dokumentach",
        "przejrzyj dokumenty", "otworz dokumenty",
    )):
        return "documents_recent", 0.99
    if "przypomn" in value and any(word in value for word in (
        "pokaz", "najbliz", "dzis", "mam", "sprawdz", "lista",
    )):
        return "reminders_overview", 0.98
    bill_signal = any(stem in value for stem in (
        "rachun", "faktur", "abonament",
    )) or any(phrase in value for phrase in (
        "ile mam zaplacic", "co mam do zaplaty", "platnosci do zaplaty",
    ))
    mail_action = any(word in value for word in (
        "odpisz", "odpowiedz", "wyslij", "napisz", "przygotuj odpowiedz",
        "przypomnij", "dodaj przypomnienie", "ustaw przypomnienie",
    ))
    if bill_signal and not mail_action:
        return "bills_overview", 0.99
    if any(phrase in value for phrase in (
        "wydatki na reklamy", "koszt reklam", "koszty reklam",
        "ile wydalismy na reklamy", "wynik reklam", "kampanie reklamowe",
        "podsumuj reklamy",
    )):
        return "advertising_overview", 0.99
    if any(word in value for word in ("trading", "tradingu", "pnl")) or any(
        phrase in value for phrase in (
            "wynik handlu", "wynik transakcji", "ile zarobilismy na handlu",
        )
    ):
        return "trading_overview", 0.99
    return None


__all__ = ["BUSINESS_DAY_INTENTS", "classify_business_day"]
