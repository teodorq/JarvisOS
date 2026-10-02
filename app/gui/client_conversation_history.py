from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

from app.core.json_store import JsonStore
from app.gui.client_result_formatter import ClientResultCard


class ClientConversationHistory:
    """Small local timeline for restoring the compact client conversation."""

    MAX_ITEMS = 8
    MAX_TEXT_LENGTH = 6_000
    _SECRET_ASSIGNMENT = re.compile(
        r"(?i)\b(api[ _-]?key|token|secret|password|has[łl]o)\b"
        r"(\s*(?:=|:)\s*|\s+(?:(?:to|jest)\s+)?)([^\s,;]+)"
    )
    _BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}")

    def __init__(self, project_root: str | Path) -> None:
        path = Path(project_root) / "data" / "client_experience" / (
            "conversation_history.json"
        )
        self.store = JsonStore(path, self._default)

    @staticmethod
    def _default() -> dict[str, object]:
        return {"schema_version": 1, "messages": []}

    def load(self) -> list[tuple[str, str, ClientResultCard | None]]:
        payload = self.store.load()
        raw_messages = (
            payload.get("messages", []) if isinstance(payload, dict) else []
        )
        restored: list[tuple[str, str, ClientResultCard | None]] = []
        for raw in list(raw_messages or [])[-self.MAX_ITEMS:]:
            if not isinstance(raw, dict):
                continue
            author = str(raw.get("author", ""))
            text = self._safe_text(raw.get("text", ""))
            if author not in {"Ty", "JARVIS"} or not text:
                continue
            card = None
            if author == "JARVIS":
                kind = str(raw.get("kind", "general"))[:40] or "general"
                title = str(raw.get("title", "JARVIS"))[:80] or "JARVIS"
                card = ClientResultCard(kind, title, text, text, text)
            restored.append((author, text, card))
        return restored

    def save(
        self,
        messages: Iterable[tuple[str, str, ClientResultCard | None]],
    ) -> None:
        serialized: list[dict[str, str]] = []
        for author, text, card in list(messages)[-self.MAX_ITEMS:]:
            safe_text = self._safe_text(text)
            if author not in {"Ty", "JARVIS"} or not safe_text:
                continue
            item = {"author": author, "text": safe_text}
            if card is not None:
                item["kind"] = str(card.kind)[:40]
                item["title"] = str(card.title)[:80]
            serialized.append(item)
        try:
            self.store.save({"schema_version": 1, "messages": serialized})
        except (OSError, RuntimeError):
            return

    def clear(self) -> None:
        try:
            self.store.save(self._default())
        except (OSError, RuntimeError):
            return

    @classmethod
    def _safe_text(cls, value: object) -> str:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        text = cls._BEARER.sub("Bearer [UKRYTO]", text)
        text = cls._SECRET_ASSIGNMENT.sub(
            lambda match: f"{match.group(1)}{match.group(2)}[UKRYTO]",
            text,
        )
        return text.strip()[: cls.MAX_TEXT_LENGTH]
