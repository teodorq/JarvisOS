from __future__ import annotations

from email.utils import getaddresses
from pathlib import Path
from typing import Any

from app.assistant.natural_language import fold_text
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.natural_actions.validation import clean_reference, is_placeholder, valid_email


class RecipientResolver:
    """Resolve names from local aliases and recent Gmail metadata."""

    def __init__(self, project_root: str | Path | None, provider: Any) -> None:
        root = resolve_project_root(project_root)
        self.provider = provider
        self.store = JsonStore(
            root / "data" / "natural_actions" / "recipient_aliases.json",
            lambda: {"version": "2.0", "aliases": {}},
        )

    def resolve(self, value: str) -> dict[str, Any]:
        reference = clean_reference(value)
        if is_placeholder(reference):
            return {"status": "INVALID", "label": reference}
        if valid_email(reference):
            return {
                "status": "RESOLVED",
                "email": reference,
                "label": reference,
                "source": "direct",
            }
        alias = self._alias(reference)
        if alias:
            return {
                "status": "RESOLVED",
                "email": alias,
                "label": reference,
                "source": "alias",
            }
        try:
            messages = self.provider.list_gmail_messages(
                query="newer_than:365d", max_results=25
            )
        except Exception:
            messages = []
        candidates = self._candidates(messages, reference)
        if len(candidates) == 1:
            email = next(iter(candidates))
            self.remember(reference, email)
            return {
                "status": "RESOLVED",
                "email": email,
                "label": reference,
                "source": "gmail",
            }
        if len(candidates) > 1:
            return {
                "status": "AMBIGUOUS",
                "label": reference,
                "options": sorted(candidates)[:4],
            }
        return {"status": "MISSING", "label": reference}

    def remember(self, label: str, email: str) -> None:
        reference = clean_reference(label)
        address = clean_reference(email)
        if is_placeholder(reference) or not valid_email(address):
            return
        data = self.store.load()
        if not isinstance(data, dict):
            data = {"version": "2.0", "aliases": {}}
        aliases = dict(data.get("aliases", {}) or {})
        aliases[fold_text(reference)] = address
        data["aliases"] = aliases
        self.store.save(data)

    def _alias(self, label: str) -> str:
        data = self.store.load()
        aliases = dict(data.get("aliases", {}) or {}) if isinstance(data, dict) else {}
        needle = fold_text(label)
        direct = str(aliases.get(needle, "") or "")
        if direct:
            return direct
        parts = [part for part in needle.split() if len(part) >= 3]
        if not parts:
            return ""
        matches = {
            str(email)
            for key, email in aliases.items()
            if all(
                part in str(key) or str(key).startswith(part[:3])
                for part in parts
            )
            and valid_email(email)
        }
        return next(iter(matches)) if len(matches) == 1 else ""

    @staticmethod
    def _candidates(messages: list[dict[str, Any]], reference: str) -> set[str]:
        needle = fold_text(reference)
        parts = [part for part in needle.split() if len(part) >= 2]
        result: set[str] = set()
        for item in messages:
            fields = (str(item.get("from", "")), str(item.get("to", "")))
            for display, address in getaddresses(fields):
                if not valid_email(address):
                    continue
                haystack = fold_text(f"{display} {address.split('@', 1)[0]}")
                if parts and all(
                    part in haystack
                    or (len(part) >= 3 and part[:3] in haystack)
                    for part in parts
                ):
                    result.add(address)
        return result
