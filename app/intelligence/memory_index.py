from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokens(value: object) -> set[str]:
    return {
        item for item in re.findall(r"[a-z0-9ąćęłńóśźż]+", str(value).casefold())
        if len(item) > 1
    }


class MemoryIndexV2:
    """B104 local ranked memory index without remote embeddings."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "intelligence" / "memory2.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.0",
            "entries": {},
            "last_search": {},
            "updated_at": "",
        }

    def remember(
        self,
        text: object,
        *,
        category: str = "general",
        tags: Iterable[str] | None = None,
        source: str = "user",
        importance: float = 0.5,
    ) -> dict[str, Any]:
        content = " ".join(str(text).split()).strip()
        if not content:
            raise ValueError("Nie można zapisać pustej informacji.")
        normalized_category = str(category).casefold().strip() or "general"
        identity = hashlib.sha256(
            f"{normalized_category}|{content.casefold()}".encode("utf-8")
        ).hexdigest()[:20]
        data = self._load()
        entries = dict(data.get("entries", {}) or {})
        previous = dict(entries.get(identity, {}) or {})
        now = utc_now()
        entry = {
            "memory_id": identity,
            "text": content[:4000],
            "category": normalized_category[:80],
            "tags": sorted({str(tag).casefold().strip() for tag in (tags or []) if str(tag).strip()})[:30],
            "source": str(source)[:80],
            "importance": max(0.0, min(float(importance), 1.0)),
            "created_at": previous.get("created_at", now),
            "updated_at": now,
            "access_count": int(previous.get("access_count", 0) or 0),
        }
        entries[identity] = entry
        data["entries"] = entries
        data["updated_at"] = now
        self.store.save(data)
        return entry

    def search(self, query: object, *, top_k: int = 5) -> list[dict[str, Any]]:
        query_text = " ".join(str(query).split()).strip()
        query_tokens = tokens(query_text)
        data = self._load()
        entries = dict(data.get("entries", {}) or {})
        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for memory_id, raw in entries.items():
            entry = dict(raw or {})
            document_tokens = tokens(
                f"{entry.get('text', '')} {entry.get('category', '')} {' '.join(entry.get('tags', []))}"
            )
            overlap = len(query_tokens & document_tokens)
            union = max(1, len(query_tokens | document_tokens))
            lexical = overlap / union
            exact = 1.0 if query_text.casefold() in str(entry.get("text", "")).casefold() else 0.0
            score = round((lexical * 0.65) + (exact * 0.2) + (float(entry.get("importance", 0.5)) * 0.15), 4)
            if score > 0.05 or not query_tokens:
                ranked.append((score, memory_id, entry))
        ranked.sort(key=lambda item: (item[0], item[2].get("updated_at", "")), reverse=True)
        results: list[dict[str, Any]] = []
        for score, memory_id, entry in ranked[: max(1, min(int(top_k), 20))]:
            entry["score"] = score
            entry["access_count"] = int(entry.get("access_count", 0) or 0) + 1
            entries[memory_id] = entry
            results.append(entry)
        data["entries"] = entries
        data["last_search"] = {
            "query": query_text,
            "result_ids": [item["memory_id"] for item in results],
            "created_at": utc_now(),
        }
        data["updated_at"] = utc_now()
        self.store.save(data)
        return results

    def forget(self, memory_id: str) -> bool:
        data = self._load()
        entries = dict(data.get("entries", {}) or {})
        removed = entries.pop(str(memory_id), None) is not None
        data["entries"] = entries
        data["updated_at"] = utc_now()
        self.store.save(data)
        return removed

    def status(self) -> dict[str, Any]:
        data = self._load()
        entries = list(dict(data.get("entries", {}) or {}).values())
        categories: dict[str, int] = {}
        for item in entries:
            category = str(item.get("category", "general"))
            categories[category] = categories.get(category, 0) + 1
        last_search = dict(data.get("last_search", {}) or {})
        return {
            "status": "MEMORY_2_READY",
            "entry_count": len(entries),
            "category_count": len(categories),
            "categories": categories,
            "last_query": last_search.get("query", ""),
            "last_result_count": len(list(last_search.get("result_ids", []) or [])),
            "most_accessed": max(entries, key=lambda item: item.get("access_count", 0), default={}),
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
