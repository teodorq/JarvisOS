from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.ai.meta_executive.meta_state import (
    MetaState,
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class MetaMemory:

    def __init__(
        self,
    ) -> None:

        self._records: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []

    def remember(
        self,
        state: MetaState | dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state_dict = self._normalize_state(
            state
        )

        meta_id = str(
            state_dict.get(
                "meta_id",
                "",
            )
        ).strip()

        if not meta_id:
            raise ValueError(
                "MetaMemory wymaga meta_id."
            )

        record = {
            "meta_id": meta_id,
            "objective": str(
                state_dict.get(
                    "objective",
                    "",
                )
            ),
            "mode": str(
                state_dict.get(
                    "mode",
                    "",
                )
            ),
            "status": str(
                state_dict.get(
                    "status",
                    "",
                )
            ),
            "selected_layer": str(
                state_dict.get(
                    "selected_layer",
                    "",
                )
            ),
            "selected_strategy": str(
                state_dict.get(
                    "selected_strategy",
                    "",
                )
            ),
            "priority": str(
                state_dict.get(
                    "priority",
                    "",
                )
            ),
            "risk_level": str(
                state_dict.get(
                    "risk_level",
                    "",
                )
            ),
            "cycle": int(
                state_dict.get(
                    "cycle",
                    0,
                )
            ),
            "state": deepcopy(
                state_dict
            ),
            "result": deepcopy(
                result
                if isinstance(
                    result,
                    dict,
                )
                else {}
            ),
            "created_at": str(
                state_dict.get(
                    "created_at",
                    _utc_now(),
                )
            ),
            "updated_at": _utc_now(),
        }

        if meta_id not in self._records:
            self._order.append(
                meta_id
            )

        self._records[
            meta_id
        ] = record

        return deepcopy(
            record
        )

    def update(
        self,
        meta_id: str,
        *,
        status: str | None = None,
        selected_layer: str | None = None,
        selected_strategy: str | None = None,
        priority: str | None = None,
        risk_level: str | None = None,
        cycle: int | None = None,
        result: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        normalized_id = str(
            meta_id
        ).strip()

        record = self._records.get(
            normalized_id
        )

        if record is None:
            return None

        if status is not None:
            record["status"] = str(
                status
            ).strip().upper()

        if selected_layer is not None:
            record["selected_layer"] = str(
                selected_layer
            ).strip().upper()

        if selected_strategy is not None:
            record["selected_strategy"] = str(
                selected_strategy
            ).strip().upper()

        if priority is not None:
            record["priority"] = str(
                priority
            ).strip().upper()

        if risk_level is not None:
            record["risk_level"] = str(
                risk_level
            ).strip().upper()

        if cycle is not None:
            record["cycle"] = int(
                cycle
            )

        if isinstance(
            result,
            dict,
        ):
            record["result"] = deepcopy(
                result
            )

        state = self._safe_dict(
            record.get(
                "state",
                {},
            )
        )

        if lessons is not None:
            state["lessons"] = self._merge_strings(
                state.get(
                    "lessons",
                    [],
                ),
                lessons,
            )

        if warnings is not None:
            state["warnings"] = self._merge_strings(
                state.get(
                    "warnings",
                    [],
                ),
                warnings,
            )

        if errors is not None:
            state["errors"] = self._merge_strings(
                state.get(
                    "errors",
                    [],
                ),
                errors,
            )

        if isinstance(
            metadata,
            dict,
        ):
            current_metadata = self._safe_dict(
                state.get(
                    "metadata",
                    {},
                )
            )
            current_metadata.update(
                deepcopy(
                    metadata
                )
            )
            state["metadata"] = current_metadata

        record["state"] = state
        record["updated_at"] = _utc_now()

        return deepcopy(
            record
        )

    def get(
        self,
        meta_id: str,
    ) -> dict[str, Any] | None:

        record = self._records.get(
            str(
                meta_id
            ).strip()
        )

        if record is None:
            return None

        return deepcopy(
            record
        )

    def list(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        normalized_limit = max(
            1,
            int(
                limit
            ),
        )

        selected_ids = self._order[
            -normalized_limit:
        ]

        selected_ids.reverse()

        return [
            deepcopy(
                self._records[
                    meta_id
                ]
            )
            for meta_id in selected_ids
            if meta_id in self._records
        ]

    def find_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:

        normalized = str(
            status
        ).strip().upper()

        return [
            deepcopy(
                record
            )
            for record in self._records.values()
            if str(
                record.get(
                    "status",
                    "",
                )
            ).strip().upper() == normalized
        ]

    def find_by_layer(
        self,
        layer_name: str,
    ) -> list[dict[str, Any]]:

        normalized = str(
            layer_name
        ).strip().upper()

        return [
            deepcopy(
                record
            )
            for record in self._records.values()
            if str(
                record.get(
                    "selected_layer",
                    "",
                )
            ).strip().upper() == normalized
        ]

    def find_by_strategy(
        self,
        strategy: str,
    ) -> list[dict[str, Any]]:

        normalized = str(
            strategy
        ).strip().upper()

        return [
            deepcopy(
                record
            )
            for record in self._records.values()
            if str(
                record.get(
                    "selected_strategy",
                    "",
                )
            ).strip().upper() == normalized
        ]

    def find_similar_objectives(
        self,
        objective: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:

        words = {
            word
            for word in str(
                objective
            ).lower().split()
            if len(
                word
            ) > 2
        }

        if not words:
            return []

        scored: list[
            tuple[int, dict[str, Any]]
        ] = []

        for record in self._records.values():
            record_words = {
                word
                for word in str(
                    record.get(
                        "objective",
                        "",
                    )
                ).lower().split()
                if len(
                    word
                ) > 2
            }

            score = len(
                words.intersection(
                    record_words
                )
            )

            if score > 0:
                scored.append(
                    (
                        score,
                        deepcopy(
                            record
                        ),
                    )
                )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            record
            for _, record in scored[
                :max(
                    1,
                    int(
                        limit
                    ),
                )
            ]
        ]

    def recurring_problems(
        self,
        minimum_count: int = 2,
    ) -> list[dict[str, Any]]:

        counter: dict[str, int] = {}

        for record in self._records.values():
            state = self._safe_dict(
                record.get(
                    "state",
                    {},
                )
            )

            for error in self._safe_string_list(
                state.get(
                    "errors",
                    [],
                )
            ):
                key = error.lower()
                counter[key] = (
                    counter.get(
                        key,
                        0,
                    )
                    + 1
                )

        result = [
            {
                "problem": key,
                "count": count,
            }
            for key, count in counter.items()
            if count >= int(
                minimum_count
            )
        ]

        result.sort(
            key=lambda item: item["count"],
            reverse=True,
        )

        return result

    def summary(
        self,
    ) -> dict[str, Any]:

        status_counts: dict[str, int] = {}
        layer_counts: dict[str, int] = {}
        strategy_counts: dict[str, int] = {}

        for record in self._records.values():
            status = str(
                record.get(
                    "status",
                    "UNKNOWN",
                )
            ).strip().upper() or "UNKNOWN"

            layer = str(
                record.get(
                    "selected_layer",
                    "NONE",
                )
            ).strip().upper() or "NONE"

            strategy = str(
                record.get(
                    "selected_strategy",
                    "NONE",
                )
            ).strip().upper() or "NONE"

            status_counts[status] = (
                status_counts.get(
                    status,
                    0,
                )
                + 1
            )

            layer_counts[layer] = (
                layer_counts.get(
                    layer,
                    0,
                )
                + 1
            )

            strategy_counts[strategy] = (
                strategy_counts.get(
                    strategy,
                    0,
                )
                + 1
            )

        return {
            "total_records": len(
                self._records
            ),
            "status_counts": status_counts,
            "layer_counts": layer_counts,
            "strategy_counts": strategy_counts,
            "recurring_problems": self.recurring_problems(),
        }

    def export_data(
        self,
    ) -> dict[str, Any]:

        return {
            "records": deepcopy(
                self._records
            ),
            "order": list(
                self._order
            ),
            "exported_at": _utc_now(),
        }

    def import_data(
        self,
        data: dict[str, Any],
    ) -> None:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "MetaMemory.import_data wymaga dict."
            )

        records = data.get(
            "records",
            {},
        )

        order = data.get(
            "order",
            [],
        )

        if not isinstance(
            records,
            dict,
        ):
            raise ValueError(
                "Pole records musi być dict."
            )

        self._records = {
            str(
                key
            ): deepcopy(
                value
            )
            for key, value in records.items()
            if isinstance(
                value,
                dict,
            )
        }

        self._order = [
            str(
                item
            )
            for item in order
            if str(
                item
            )
            in self._records
        ]

        for meta_id in self._records:
            if meta_id not in self._order:
                self._order.append(
                    meta_id
                )

    def clear(
        self,
    ) -> None:

        self._records.clear()
        self._order.clear()

    def _normalize_state(
        self,
        state: MetaState | dict[str, Any],
    ) -> dict[str, Any]:

        if isinstance(
            state,
            MetaState,
        ):
            return state.to_dict()

        if isinstance(
            state,
            dict,
        ):
            return deepcopy(
                state
            )

        raise TypeError(
            "MetaMemory wymaga MetaState lub dict."
        )

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return deepcopy(
                value
            )

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (list, tuple, set),
        ):
            return []

        result: list[str] = []

        for item in value:
            text = str(
                item
            ).strip()

            if text:
                result.append(
                    text
                )

        return result

    def _merge_strings(
        self,
        current: Any,
        incoming: Any,
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for item in (
            self._safe_string_list(
                current
            )
            + self._safe_string_list(
                incoming
            )
        ):
            key = item.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                item
            )

        return result
