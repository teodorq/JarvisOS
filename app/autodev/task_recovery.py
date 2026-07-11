from __future__ import annotations

from typing import Any


class TaskRecovery:

    INTERRUPTED_STATUSES = {
        "RUNNING",
        "PROCESSING",
        "IN_PROGRESS",
    }

    def recover(
        self,
        controller: Any,
    ) -> dict[str, Any]:
        list_tasks = getattr(
            controller,
            "list_tasks",
            None,
        )

        if not callable(list_tasks):
            return {
                "success": False,
                "status": "UNSUPPORTED",
                "recovered": [],
            }

        tasks = list_tasks()
        recovered: list[str] = []
        failed: list[dict[str, str]] = []

        retry_task = getattr(
            controller,
            "retry_task",
            None,
        )

        if not callable(retry_task):
            return {
                "success": True,
                "status": "NO_RETRY_METHOD",
                "recovered": [],
            }

        for task in tasks:
            status = str(
                task.get("status", "")
            ).upper()

            if status not in self.INTERRUPTED_STATUSES:
                continue

            task_id = str(
                task.get("task_id", "")
            ).strip()

            if not task_id:
                continue

            try:
                retry_task(
                    task_id,
                    reset_attempts=False,
                )
                recovered.append(task_id)
            except Exception as error:
                failed.append(
                    {
                        "task_id": task_id,
                        "error": (
                            f"{type(error).__name__}: {error}"
                        ),
                    }
                )

        return {
            "success": not failed,
            "status": (
                "RECOVERED"
                if recovered
                else "NOTHING_TO_RECOVER"
            ),
            "recovered": recovered,
            "failed": failed,
        }
