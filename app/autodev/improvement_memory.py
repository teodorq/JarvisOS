from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ImprovementRecord:
    success: bool
    status: str
    created_at: str
    task: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] = field(default_factory=dict)
    patch: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementMemory:
    """
    Prosta trwała pamięć autonomicznych ulepszeń.

    Dane są zapisywane do JSON.
    Klasa nie modyfikuje kodu projektu.
    """

    def __init__(
        self,
        storage_path: str = (
            default_project_path("data", "autodev") + "/"
            "improvement_memory.json"
        ),
        max_records: int = 500,
    ) -> None:
        self.storage_path = Path(
            storage_path
        )
        self.max_records = max_records
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []

        self._load()

    def remember(
        self,
        *,
        success: bool,
        status: str,
        task: dict[str, Any] | None = None,
        workflow: dict[str, Any] | None = None,
        patch: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        execution: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
    ) -> dict[str, Any]:

        record = ImprovementRecord(
            success=bool(success),
            status=str(status),
            created_at=datetime.now().isoformat(),
            task=dict(task or {}),
            workflow=dict(workflow or {}),
            patch=dict(patch or {}),
            validation=dict(validation or {}),
            execution=dict(execution or {}),
            lessons=list(lessons or []),
        ).to_dict()

        with self._lock:
            self._records.append(
                record
            )

            if len(self._records) > self.max_records:
                self._records = self._records[
                    -self.max_records:
                ]

            self._save()

        return dict(
            record
        )

    def list_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:

        with self._lock:
            records = list(
                self._records
            )

        if limit is not None:
            records = records[
                -max(0, int(limit)):
            ]

        return [
            dict(record)
            for record in records
        ]

    def last(
        self,
    ) -> dict[str, Any] | None:

        with self._lock:
            if not self._records:
                return None

            return dict(
                self._records[-1]
            )

    def summary(
        self,
    ) -> dict[str, Any]:

        with self._lock:
            total = len(
                self._records
            )

            successful = sum(
                1
                for record in self._records
                if record.get(
                    "success"
                ) is True
            )

            failed = total - successful

            by_status: dict[str, int] = {}

            for record in self._records:
                status = str(
                    record.get(
                        "status",
                        "UNKNOWN",
                    )
                )

                by_status[status] = (
                    by_status.get(
                        status,
                        0,
                    )
                    + 1
                )

            return {
                "total_records": total,
                "successful": successful,
                "failed": failed,
                "by_status": by_status,
                "storage_path": str(
                    self.storage_path
                ),
            }

    def clear(
        self,
    ) -> None:

        with self._lock:
            self._records = []
            self._save()

    def _load(
        self,
    ) -> None:

        with self._lock:
            if not self.storage_path.exists():
                self._records = []
                return

            try:
                payload = json.loads(
                    self.storage_path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                self._records = []
                return

            if isinstance(
                payload,
                list,
            ):
                self._records = [
                    dict(item)
                    for item in payload
                    if isinstance(
                        item,
                        dict,
                    )
                ][-self.max_records:]

            else:
                self._records = []

    def _save(
        self,
    ) -> None:

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_suffix(
                self.storage_path.suffix
                + ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                self._records,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )
