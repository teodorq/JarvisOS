from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.common import bounded, utc_iso


class RuntimePerformanceCenter:
    """B112 bounded performance probes and local-state compaction."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.project_root / "data" / "stability" / "performance.json",
            lambda: {"snapshots": [], "maintenance": []},
        )

    def probe(self) -> dict[str, Any]:
        json_ms = self._json_probe_ms()
        file_ms = self._file_probe_ms()
        rss_mb = self._rss_mb()
        score = 100
        if json_ms > 75:
            score -= 20
        if file_ms > 100:
            score -= 20
        if rss_mb and rss_mb > 1024:
            score -= 25
        snapshot = {
            "created_at": utc_iso(),
            "status": "HEALTHY" if score >= 80 else "WARNING",
            "score": max(0, score),
            "json_roundtrip_ms": round(json_ms, 3),
            "file_read_ms": round(file_ms, 3),
            "rss_mb": round(rss_mb, 2),
            "cpu_count": os.cpu_count() or 1,
            "recommendations": self._recommendations(json_ms, file_ms, rss_mb),
        }
        state = self.store.load()
        state["snapshots"] = bounded(list(state.get("snapshots", [])) + [snapshot], 60)
        self.store.save(state)
        return snapshot

    def compact(self) -> dict[str, Any]:
        state = self.store.load()
        before = len(list(state.get("snapshots", [])))
        state["snapshots"] = bounded(list(state.get("snapshots", [])), 20)
        action = {
            "created_at": utc_iso(),
            "action": "COMPACT_STABILITY_HISTORY",
            "removed": max(0, before - len(state["snapshots"])),
        }
        state["maintenance"] = bounded(list(state.get("maintenance", [])) + [action], 30)
        self.store.save(state)
        return action

    def status(self) -> dict[str, Any]:
        state = self.store.load()
        snapshots = list(state.get("snapshots", []))
        latest = dict(snapshots[-1]) if snapshots else {}
        return {
            "status": "RUNTIME_PERFORMANCE_READY",
            "snapshot_count": len(snapshots),
            "latest_score": latest.get("score", 0),
            "latest_status": latest.get("status", "NOT_RUN"),
            "rss_mb": latest.get("rss_mb", 0),
            "json_roundtrip_ms": latest.get("json_roundtrip_ms", 0),
            "file_read_ms": latest.get("file_read_ms", 0),
            "latest_snapshot": latest,
        }

    @staticmethod
    def _json_probe_ms() -> float:
        payload = {"jarvis": list(range(200)), "status": "READY"}
        started = time.perf_counter()
        for _ in range(100):
            json.loads(json.dumps(payload))
        return (time.perf_counter() - started) * 1000

    def _file_probe_ms(self) -> float:
        source = self.project_root / "app" / "ai" / "brain.py"
        started = time.perf_counter()
        if source.is_file():
            source.read_bytes()[:262144]
        return (time.perf_counter() - started) * 1000

    @staticmethod
    def _rss_mb() -> float:
        try:
            import psutil  # type: ignore
            return float(psutil.Process().memory_info().rss) / (1024 * 1024)
        except (ImportError, OSError):
            return 0.0

    @staticmethod
    def _recommendations(json_ms: float, file_ms: float, rss_mb: float) -> list[str]:
        items: list[str] = []
        if json_ms > 75:
            items.append("Ograniczyć częstotliwość zapisów dużych struktur JSON.")
        if file_ms > 100:
            items.append("Sprawdzić obciążenie dysku i skanowanie antywirusowe.")
        if rss_mb > 1024:
            items.append("Przejrzeć długotrwałe cache i nieaktywne modele.")
        return items or ["Brak krytycznych zaleceń wydajnościowych."]
