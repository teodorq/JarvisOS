from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass(slots=True)
class BacklogItem:

    task_id: str
    title: str
    description: str
    target: str
    priority_score: float
    severity: str = "MEDIUM"
    status: str = "PENDING"
    recommendation: str = ""
    source: str = "BacklogManager"
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    created_at: str = field(
        default_factory=lambda: (
            datetime.now().isoformat()
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "target": self.target,
            "priority_score": self.priority_score,
            "severity": self.severity,
            "status": self.status,
            "recommendation": self.recommendation,
            "source": self.source,
            "metadata": dict(
                self.metadata
            ),
            "created_at": self.created_at,
        }


class BacklogManager:

    def __init__(
        self,
        max_items: int = 200,
    ) -> None:

        self.max_items = max(
            1,
            int(
                max_items
            ),
        )

        self.items: list[
            BacklogItem
        ] = []

    def add(
        self,
        task_data: dict[str, Any],
    ) -> BacklogItem:

        existing = self.find_duplicate(
            title=str(
                task_data.get(
                    "title",
                    "",
                )
            ),
            target=str(
                task_data.get(
                    "target",
                    "",
                )
            ),
        )

        if existing is not None:
            return existing

        if len(
            self.items
        ) >= self.max_items:
            raise RuntimeError(
                "Backlog osiągnął maksymalny rozmiar."
            )

        item = BacklogItem(
            task_id=str(
                task_data.get(
                    "task_id",
                    "",
                )
                or uuid.uuid4()
            ),
            title=str(
                task_data.get(
                    "title",
                    "",
                )
            ).strip(),
            description=str(
                task_data.get(
                    "description",
                    "",
                )
            ).strip(),
            target=str(
                task_data.get(
                    "target",
                    "",
                )
            ).strip(),
            priority_score=float(
                task_data.get(
                    "priority_score",
                    0.0,
                )
            ),
            severity=str(
                task_data.get(
                    "severity",
                    "MEDIUM",
                )
            ).upper(),
            recommendation=str(
                task_data.get(
                    "recommendation",
                    "",
                )
            ).strip(),
            source=str(
                task_data.get(
                    "source",
                    "BacklogManager",
                )
            ),
            metadata=dict(
                task_data.get(
                    "metadata"
                )
                or {}
            ),
        )

        self.items.append(
            item
        )

        self._sort()

        return item

    def add_many(
        self,
        tasks: list[
            dict[str, Any]
        ],
    ) -> list[
        BacklogItem
    ]:

        added: list[
            BacklogItem
        ] = []

        for task in tasks:
            added.append(
                self.add(
                    task
                )
            )

        return added

    def next_item(
        self,
    ) -> BacklogItem | None:

        self._sort()

        for item in self.items:
            if item.status == "PENDING":
                return item

        return None

    def mark_running(
        self,
        task_id: str,
    ) -> BacklogItem:

        item = self.require(
            task_id
        )

        item.status = "RUNNING"

        return item

    def mark_completed(
        self,
        task_id: str,
    ) -> BacklogItem:

        item = self.require(
            task_id
        )

        item.status = "COMPLETED"

        return item

    def mark_failed(
        self,
        task_id: str,
        error: str = "",
    ) -> BacklogItem:

        item = self.require(
            task_id
        )

        item.status = "FAILED"

        if error:
            item.metadata[
                "error"
            ] = error

        return item

    def require(
        self,
        task_id: str,
    ) -> BacklogItem:

        for item in self.items:
            if item.task_id == task_id:
                return item

        raise KeyError(
            f"Nie znaleziono zadania: {task_id}"
        )

    def find_duplicate(
        self,
        *,
        title: str,
        target: str,
    ) -> BacklogItem | None:

        normalized_title = str(
            title
        ).strip().casefold()

        normalized_target = str(
            target
        ).strip().casefold()

        for item in self.items:
            if (
                item.title.casefold()
                == normalized_title
                and item.target.casefold()
                == normalized_target
                and item.status
                not in {
                    "COMPLETED",
                    "CANCELLED",
                }
            ):
                return item

        return None

    def list_items(
        self,
        status: str | None = None,
    ) -> list[
        dict[str, Any]
    ]:

        items = self.items

        if status:
            normalized = status.upper()

            items = [
                item
                for item in items
                if item.status == normalized
            ]

        return [
            item.to_dict()
            for item in items
        ]

    def summary(
        self,
    ) -> dict[str, Any]:

        by_status: dict[
            str,
            int
        ] = {}

        for item in self.items:
            by_status[
                item.status
            ] = (
                by_status.get(
                    item.status,
                    0,
                )
                + 1
            )

        next_item = self.next_item()

        return {
            "total": len(
                self.items
            ),
            "by_status": by_status,
            "next_task": (
                next_item.to_dict()
                if next_item
                else None
            ),
        }

    def _sort(
        self,
    ) -> None:

        self.items.sort(
            key=lambda item: (
                item.priority_score,
                item.created_at,
            ),
            reverse=True,
        )
