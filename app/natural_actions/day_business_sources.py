from __future__ import annotations

import re
from typing import Any

from app.assistant.natural_language import fold_text


class EmailFinancialAnalyzer:
    """Extract only explicit money values from Gmail metadata and snippets."""

    BILL_TERMS = (
        "faktura", "rachunek", "do zaplaty", "platnosc", "abonament",
        "invoice", "payment due", "polkomtel", "plus gsm", "orange",
        "play", "t-mobile", "energia", "prad", "gaz", "internet",
    )
    AD_TERMS = (
        "google ads", "meta ads", "facebook ads", "tiktok ads",
        "reklama", "kampania reklamowa", "ad spend", "billing ads",
    )
    AMOUNT = re.compile(
        r"(?<!\w)(\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})?)\s*"
        r"(zł|pln|eur|€|usd|\$)",
        re.IGNORECASE,
    )

    @classmethod
    def analyze(cls, messages: list[dict[str, Any]]) -> dict[str, Any]:
        bills: list[dict[str, Any]] = []
        advertising: list[dict[str, Any]] = []
        for raw in messages:
            item = dict(raw)
            text = " ".join(str(item.get(key, "")) for key in (
                "from", "subject", "snippet",
            ))
            folded = fold_text(text)
            record = cls._record(item, text)
            if any(term in folded for term in cls.BILL_TERMS):
                bills.append(record)
            if any(term in folded for term in cls.AD_TERMS):
                advertising.append(record)
        return {
            "bills": bills,
            "advertising": advertising,
            "bill_totals": cls.totals(bills),
            "advertising_totals": cls.totals(advertising),
        }

    @classmethod
    def _record(cls, message: dict[str, Any], text: str) -> dict[str, Any]:
        match = cls.AMOUNT.search(text)
        amount = cls._number(match.group(1)) if match else None
        currency = cls._currency(match.group(2)) if match else ""
        return {
            "subject": cls._clean(message.get("subject"), 180),
            "sender": cls._clean(message.get("from"), 140),
            "date": cls._clean(message.get("date"), 100),
            "amount": amount,
            "currency": currency,
        }

    @staticmethod
    def totals(records: list[dict[str, Any]]) -> dict[str, float]:
        result: dict[str, float] = {}
        for item in records:
            amount = item.get("amount")
            currency = str(item.get("currency", ""))
            if amount is None or not currency:
                continue
            result[currency] = round(result.get(currency, 0.0) + float(amount), 2)
        return result

    @staticmethod
    def _number(value: str) -> float | None:
        compact = value.replace(" ", "")
        if "," in compact:
            normalized = compact.replace(".", "").replace(",", ".")
        elif compact.count(".") == 1 and len(compact.rsplit(".", 1)[1]) == 2:
            normalized = compact
        else:
            normalized = compact.replace(".", "")
        try:
            return round(float(normalized), 2)
        except ValueError:
            return None

    @staticmethod
    def _currency(value: str) -> str:
        return {"ZŁ": "PLN", "€": "EUR", "$": "USD"}.get(
            value.upper(), value.upper()
        )

    @staticmethod
    def _clean(value: object, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]


def money_text(totals: dict[str, float]) -> str:
    if not totals:
        return "bez odczytanej kwoty"
    return ", ".join(
        f"{amount:,.2f} {currency}".replace(",", " ")
        for currency, amount in sorted(totals.items())
    )


__all__ = ["EmailFinancialAnalyzer", "money_text"]
