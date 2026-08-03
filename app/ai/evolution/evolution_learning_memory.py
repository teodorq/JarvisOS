from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class EvolutionLearningMemory:
    """Trwała pamięć sukcesów, porażek i rollbacków AutoDev."""

    def __init__(
        self,
        storage_path: str | Path = (
            "data/evolution/evolution_learning_memory.json"
        ),
        max_entries: int = 2000,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.max_entries = max(1, int(max_entries))
        self.entries: list[dict[str, Any]] = []
        self._ensure_storage()
        self.load()

    def remember(
        self,
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_task = dict(task or {})
        normalized_result = dict(result or {})
        status = str(normalized_result.get("status", "UNKNOWN")).upper()
        success = bool(
            normalized_result.get("success", status in {"COMPLETED", "SUCCESS"})
        )
        rollback = bool(
            normalized_result.get("rollback")
            or normalized_result.get("rolled_back")
            or status in {"ROLLBACK", "ROLLED_BACK"}
        )

        entry = {
            "memory_id": f"evolution_learning_{uuid4().hex}",
            "task_id": str(
                normalized_task.get("task_id")
                or normalized_task.get("id")
                or ""
            ),
            "title": str(normalized_task.get("title", "")),
            "target": str(normalized_task.get("target", "")),
            "source": str(normalized_task.get("source", "")),
            "tags": list(normalized_task.get("tags") or []),
            "success": success,
            "rollback": rollback,
            "status": status,
            "attempts": self._int(normalized_result.get("attempts", 1), 1),
            "duration_seconds": self._float(
                normalized_result.get("duration_seconds", 0.0),
                0.0,
            ),
            "result": normalized_result,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        self.save()
        return dict(entry)

    def statistics_for(
        self,
        task: dict[str, Any],
    ) -> dict[str, float]:
        matching = self._matching_entries(task)
        if not matching:
            return {
                "samples": 0.0,
                "success_probability": 65.0,
                "rollback_rate": 15.0,
                "learning_bonus": 50.0,
            }

        total = float(len(matching))
        successes = sum(1 for item in matching if item.get("success"))
        rollbacks = sum(1 for item in matching if item.get("rollback"))
        success_probability = (successes / total) * 100.0
        rollback_rate = (rollbacks / total) * 100.0

        sample_bonus = min(total * 5.0, 25.0)
        quality_bonus = max(0.0, success_probability - rollback_rate) * 0.5
        learning_bonus = min(100.0, 25.0 + sample_bonus + quality_bonus)

        return {
            "samples": total,
            "success_probability": round(success_probability, 2),
            "rollback_rate": round(rollback_rate, 2),
            "learning_bonus": round(learning_bonus, 2),
        }

    def summary(self) -> dict[str, Any]:
        total = len(self.entries)
        successes = sum(1 for item in self.entries if item.get("success"))
        rollbacks = sum(1 for item in self.entries if item.get("rollback"))
        return {
            "entries_count": total,
            "successes": successes,
            "failures": total - successes,
            "rollbacks": rollbacks,
            "success_rate": round((successes / total) * 100.0, 2) if total else 0.0,
            "rollback_rate": round((rollbacks / total) * 100.0, 2) if total else 0.0,
        }

    def load(self) -> None:
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = []
        self.entries = [dict(item) for item in raw if isinstance(item, dict)]
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def save(self) -> None:
        self._ensure_storage()
        self.storage_path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _matching_entries(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        target = str(task.get("target", "")).casefold()
        source = str(task.get("source", "")).casefold()
        tags = {str(tag).casefold() for tag in task.get("tags", [])}

        matching: list[dict[str, Any]] = []
        for entry in self.entries:
            entry_target = str(entry.get("target", "")).casefold()
            entry_source = str(entry.get("source", "")).casefold()
            entry_tags = {str(tag).casefold() for tag in entry.get("tags", [])}
            if target and entry_target == target:
                matching.append(entry)
            elif source and entry_source == source:
                matching.append(entry)
            elif tags and tags.intersection(entry_tags):
                matching.append(entry)
        return matching

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]", encoding="utf-8")

    @staticmethod
    def _int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
