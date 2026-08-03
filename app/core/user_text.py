from __future__ import annotations

import re


_STAGE_CODE = re.compile(
    r"(?<![A-Za-z0-9])B\d{2,3}(?:\.\d+)?"
    r"(?:\s*[–—-]\s*B?\d{2,3}(?:\.\d+)?)?"
    r"(?![A-Za-z0-9])(?:\s*[:•]\s*)?",
    flags=re.I,
)
_MACHINE_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,}\b")
_STATUS_WORDS = {
    "COMPLETED": "zakończone",
    "READY": "gotowe",
    "PENDING": "oczekuje",
    "FAILED": "niepowodzenie",
    "RUNNING": "w trakcie",
    "STOPPED": "zatrzymane",
    "RETRY": "ponawiam",
}
_MACHINE_PHRASES = {
    "NATURAL_CONVERSATION": "naturalna rozmowa",
    "RELIABLE_DESKTOP": "obsługa pulpitu",
    "DAILY_PRODUCTIVITY_SUITE_READY": "narzędzia codziennej pracy są gotowe",
    "DAILY_PRODUCTIVITY_REPORTING_READY": "raporty produktywności są gotowe",
    "STABILITY_RECOVERY_BETA_SUITE_READY": "stabilność i odzyskiwanie są gotowe",
    "ASSISTANT_1_2_SUITE_READY": "asystent jest gotowy",
    "REAL_ONLINE_ASSISTANT_RC_READY": "asystent online jest gotowy",
}


def naturalize_user_text(
    value: object,
    *,
    maximum: int = 6000,
    preserve_lines: bool = True,
) -> str:
    """Return readable UI text without internal milestone identifiers."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _STAGE_CODE.sub(_remove_known_stage_code, text)
    text = _MACHINE_TOKEN.sub(_humanize_machine_token, text)
    for technical, natural in _STATUS_WORDS.items():
        text = re.sub(rf"\b{technical}\b", natural, text, flags=re.I)
    text = re.sub(r"\bFaza\s*:\s*", "Stan: ", text, flags=re.I)
    text = re.sub(r"\bStatus techniczny\s*:\s*", "Stan: ", text, flags=re.I)
    text = text.replace("Auto-approve", "Automatyczne zatwierdzanie")

    lines = [_clean_line(line) for line in text.splitlines()]
    if preserve_lines:
        text = "\n".join(line for line in lines if line).strip()
    else:
        text = " ".join(line for line in lines if line).strip()
    if len(text) <= maximum:
        return text
    return text[: max(1, maximum - 1)].rstrip(" ,;:-") + "…"


def contains_stage_code(value: object) -> bool:
    """Report whether text still contains a user-facing milestone code."""
    return any(
        _is_known_stage(match) for match in _STAGE_CODE.finditer(str(value or ""))
    )


def _humanize_machine_token(match: re.Match[str]) -> str:
    token = match.group(0)
    known = _MACHINE_PHRASES.get(token)
    if known:
        return known
    if token.endswith(tuple(f"_{word}" for word in _STATUS_WORDS)):
        return " ".join(token.lower().split("_"))
    return token


def _remove_known_stage_code(match: re.Match[str]) -> str:
    if not _is_known_stage(match) or _inside_quoted_text(match):
        return match.group(0)
    return ""


def _inside_quoted_text(match: re.Match[str]) -> bool:
    prefix = match.string[:match.start()]
    suffix = match.string[match.end():]
    for opening, closing in (("„", "”"), ("“", "”"), ("«", "»")):
        if prefix.rfind(opening) > prefix.rfind(closing) and closing in suffix:
            return True
    for quote in ('"', "'"):
        if prefix.count(quote) % 2 and quote in suffix:
            return True
    return False


def _is_known_stage(match: re.Match[str]) -> bool:
    number = re.search(r"\d{2,3}", match.group(0))
    return bool(number and int(number.group(0)) <= 380)


def _clean_line(value: str) -> str:
    line = " ".join(value.split())
    line = re.sub(r"\s+([,.;:!?])", r"\1", line)
    line = re.sub(r"([:•])\s*([:•])", r"\1", line)
    line = re.sub(r"\s*[•]\s*(?=$)", "", line)
    return line.strip(" \t:•–—-")
