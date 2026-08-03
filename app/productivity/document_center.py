from __future__ import annotations

from pathlib import Path
from typing import Any
import zipfile
import xml.etree.ElementTree as ET

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.productivity.common import clean_text, safe_project_path, sha256_file, tokens, utc_now


_TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".py", ".log", ".ini", ".cfg", ".yaml", ".yml"}
_SUPPORTED = _TEXT_EXTENSIONS | {".docx", ".pdf"}


class LocalDocumentCenter:
    """B108 safe local indexing inside the JARVIS project tree."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.root / "data" / "productivity" / "documents.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "documents": {},
            "last_scan": {},
            "last_search": {},
            "updated_at": "",
        }

    def create_demo(self) -> Path:
        directory = self.root / "AI_PLIKI" / "documents"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "JARVIS_B108_DEMO.txt"
        path.write_text(
            "JARVIS OS B108\nDokument demonstracyjny do lokalnego indeksu.\n"
            "Bez wysyłania danych i bez dostępu do chmury.\n",
            encoding="utf-8",
        )
        return path

    def scan(self, path: str | Path | None = None) -> dict[str, Any]:
        target = safe_project_path(self.root, path, default_relative="AI_PLIKI")
        target.mkdir(parents=True, exist_ok=True)
        data = self._load()
        documents = dict(data.get("documents", {}) or {})
        scanned = 0
        skipped = 0
        for file_path in target.rglob("*"):
            if scanned >= 5000:
                break
            if not file_path.is_file() or file_path.suffix.casefold() not in _SUPPORTED:
                continue
            try:
                record = self._record(file_path)
            except (OSError, UnicodeError, zipfile.BadZipFile, ET.ParseError):
                skipped += 1
                continue
            documents[record["path"]] = record
            scanned += 1
        now = utc_now()
        data.update({
            "documents": documents,
            "last_scan": {"path": str(target), "scanned": scanned, "skipped": skipped, "created_at": now},
            "updated_at": now,
        })
        self.store.save(data)
        return dict(data["last_scan"])

    def search(self, query: object, *, top_k: int = 10) -> list[dict[str, Any]]:
        query_text = clean_text(query, limit=300)
        query_tokens = tokens(query_text)
        data = self._load()
        ranked: list[tuple[float, dict[str, Any]]] = []
        for raw in dict(data.get("documents", {}) or {}).values():
            item = dict(raw)
            document_tokens = tokens(f"{item.get('name', '')} {item.get('snippet', '')} {item.get('path', '')}")
            overlap = len(query_tokens & document_tokens)
            exact = 1 if query_text.casefold() in f"{item.get('name', '')} {item.get('snippet', '')}".casefold() else 0
            score = (overlap * 2.0) + exact
            if score > 0 or not query_tokens:
                item["score"] = score
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1].get("modified_at", "")), reverse=True)
        results = [item for _, item in ranked[: max(1, min(int(top_k), 50))]]
        data["last_search"] = {"query": query_text, "result_count": len(results), "created_at": utc_now()}
        self.store.save(data)
        return results

    def recent(self, top_k: int = 10) -> list[dict[str, Any]]:
        documents = [
            dict(item) for item in
            dict(self._load().get("documents", {}) or {}).values()
        ]
        documents.sort(
            key=lambda item: int(item.get("modified_at", 0) or 0), reverse=True
        )
        return documents[:max(1, min(int(top_k), 50))]

    def status(self) -> dict[str, Any]:
        data = self._load()
        documents = list(dict(data.get("documents", {}) or {}).values())
        last_scan = dict(data.get("last_scan", {}) or {})
        last_search = dict(data.get("last_search", {}) or {})
        return {
            "status": "LOCAL_DOCUMENT_CENTER_READY",
            "document_count": len(documents),
            "text_document_count": sum(item.get("content_indexed") for item in documents),
            "last_scan_path": last_scan.get("path", ""),
            "last_scan_count": last_scan.get("scanned", 0),
            "last_query": last_search.get("query", ""),
            "last_result_count": last_search.get("result_count", 0),
            "remote_indexing": False,
        }

    def _record(self, path: Path) -> dict[str, Any]:
        snippet = ""
        content_indexed = False
        suffix = path.suffix.casefold()
        if suffix in _TEXT_EXTENSIONS:
            snippet = path.read_text(encoding="utf-8", errors="ignore")[:12000]
            content_indexed = True
        elif suffix == ".docx":
            snippet = self._docx_text(path)[:12000]
            content_indexed = bool(snippet)
        stat = path.stat()
        return {
            "path": str(path.resolve(strict=False)),
            "name": path.name,
            "extension": suffix,
            "size": stat.st_size,
            "modified_at": stat.st_mtime_ns,
            "sha256": sha256_file(path),
            "snippet": clean_text(snippet, limit=12000),
            "content_indexed": content_indexed,
            "indexed_at": utc_now(),
        }

    @staticmethod
    def _docx_text(path: Path) -> str:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
