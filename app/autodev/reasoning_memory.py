from __future__ import annotations

from datetime import datetime
from typing import Any


class ReasoningMemory:

    def __init__(
        self,
        max_records: int = 500,
    ) -> None:

        self.max_records = max(
            1,
            int(max_records),
        )

        self.history: list[Any] = []

    def remember(
        self,
        result: Any,
    ) -> Any:

        self.history.append(result)

        if len(self.history) > self.max_records:
            self.history = self.history[
                -self.max_records:
            ]

        return result

    def last(
        self,
    ) -> Any | None:

        if not self.history:
            return None

        return self.history[-1]

    def count(
        self,
    ) -> int:

        return len(self.history)

    def clear(
        self,
    ) -> None:

        self.history.clear()

    def successful(
        self,
    ) -> list[Any]:

        return [
            item
            for item in self.history
            if self._success(item)
        ]

    def failed(
        self,
    ) -> list[Any]:

        return [
            item
            for item in self.history
            if not self._success(item)
        ]

    def lessons(
        self,
        limit: int = 20,
    ) -> list[str]:

        collected: list[str] = []

        for item in reversed(self.history):
            data = self._as_dict(item)

            for lesson in data.get(
                "lessons",
                [],
            ):
                text = str(lesson).strip()

                if text and text not in collected:
                    collected.append(text)

                if len(collected) >= limit:
                    return collected

        return collected

    def summary_dict(
        self,
    ) -> dict[str, Any]:

        total = self.count()
        successful = len(self.successful())
        failed = total - successful

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (
                round(
                    successful / total,
                    4,
                )
                if total
                else 0.0
            ),
            "last": (
                self._as_dict(self.last())
                if self.last() is not None
                else None
            ),
            "lessons": self.lessons(),
            "updated_at": datetime.now().isoformat(),
        }

    def summary(
        self,
    ) -> str:

        data = self.summary_dict()

        lines = [
            "REASONING MEMORY",
            f"Liczba analiz: {data['total']}",
            f"Udane: {data['successful']}",
            f"Nieudane: {data['failed']}",
            (
                "Skuteczność: "
                f"{data['success_rate'] * 100:.1f}%"
            ),
            "",
        ]

        if data["lessons"]:
            lines.append("Wnioski:")

            for lesson in data["lessons"][:10]:
                lines.append(f"- {lesson}")

        return "\n".join(lines)

    def _success(
        self,
        item: Any,
    ) -> bool:

        data = self._as_dict(item)

        if "success" in data:
            return bool(data["success"])

        return True

    def _as_dict(
        self,
        item: Any,
    ) -> dict[str, Any]:

        if item is None:
            return {}

        if isinstance(item, dict):
            return dict(item)

        to_dict = getattr(
            item,
            "to_dict",
            None,
        )

        if callable(to_dict):
            converted = to_dict()

            if isinstance(converted, dict):
                return converted

        as_dict = getattr(
            item,
            "as_dict",
            None,
        )

        if callable(as_dict):
            converted = as_dict()

            if isinstance(converted, dict):
                return converted

        return {
            "goal": str(
                getattr(item, "goal", "")
            ),
            "confidence": getattr(
                item,
                "confidence",
                None,
            ),
            "success": getattr(
                item,
                "success",
                True,
            ),
            "value": str(item),
        }
