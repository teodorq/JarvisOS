from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class MultiFileRunStore:
    """Atomic bounded history for feature and refactor runs."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 100,
        filename: str = "multi_file_feature_runs.json",
    ) -> None:
        self.paths = ProjectPaths.from_value(
            project_root
        )
        self.max_records = max(
            10,
            int(max_records),
        )
        safe_filename = Path(
            str(filename)
        ).name

        if (
            not safe_filename.endswith(
                ".json"
            )
            or safe_filename in {
                "",
                ".",
                "..",
            }
        ):
            raise ValueError(
                "Nieprawidłowa nazwa pliku historii."
            )

        self.path = (
            self.paths.autodev_data
            / safe_filename
        )
        self._store = JsonStore(
            self.path,
            lambda: {
                "version": 1,
                "updated_at": "",
                "runs": {},
                "order": [],
            },
        )

    def save(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = str(
            run.get(
                "run_id",
                "",
            )
        ).strip()

        if not run_id:
            raise ValueError(
                "run_id nie może być pusty."
            )

        payload = self._normalized_payload(
            self._store.load()
        )
        runs = payload["runs"]
        order = payload["order"]
        stored = dict(run)
        stored["run_id"] = run_id
        runs[run_id] = stored

        if run_id in order:
            order.remove(run_id)

        order.append(run_id)

        while len(order) > self.max_records:
            removed = order.pop(0)
            runs.pop(
                removed,
                None,
            )

        payload["updated_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
        self._store.save(
            payload
        )

        return dict(stored)

    def get(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        payload = self._normalized_payload(
            self._store.load()
        )
        value = payload["runs"].get(
            str(run_id).strip()
        )

        return (
            dict(value)
            if isinstance(
                value,
                dict,
            )
            else None
        )

    def list_recent(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._normalized_payload(
            self._store.load()
        )
        safe_limit = min(
            self.max_records,
            max(
                1,
                int(limit),
            ),
        )
        selected = payload["order"][-safe_limit:]

        return [
            dict(
                payload["runs"][run_id]
            )
            for run_id in reversed(
                selected
            )
            if isinstance(
                payload["runs"].get(
                    run_id
                ),
                dict,
            )
        ]

    @staticmethod
    def _normalized_payload(
        value: Any,
    ) -> dict[str, Any]:
        payload = (
            dict(value)
            if isinstance(
                value,
                dict,
            )
            else {}
        )
        runs = payload.get(
            "runs",
            {},
        )
        order = payload.get(
            "order",
            [],
        )

        if not isinstance(
            runs,
            dict,
        ):
            runs = {}

        if not isinstance(
            order,
            list,
        ):
            order = []

        normalized_order = [
            str(run_id)
            for run_id in order
            if str(run_id) in runs
        ]

        for run_id in runs:
            text = str(run_id)

            if text not in normalized_order:
                normalized_order.append(
                    text
                )

        return {
            "version": 1,
            "updated_at": str(
                payload.get(
                    "updated_at",
                    "",
                )
            ),
            "runs": {
                str(key): dict(item)
                for key, item in runs.items()
                if isinstance(
                    item,
                    dict,
                )
            },
            "order": normalized_order,
        }
