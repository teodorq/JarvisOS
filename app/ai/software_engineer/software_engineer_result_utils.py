from __future__ import annotations

from typing import Any


def collect_execution_errors(
    execution: dict[str, Any],
) -> list[str]:
    values: list[str] = []

    direct = execution.get(
        "errors",
        [],
    )

    if isinstance(
        direct,
        (list, tuple),
    ):
        values.extend(
            str(item)
            for item in direct
            if str(item).strip()
        )

    final_result = execution.get(
        "final_result",
        {},
    )

    if isinstance(
        final_result,
        dict,
    ):
        final_errors = final_result.get(
            "errors",
            [],
        )

        if isinstance(
            final_errors,
            (list, tuple),
        ):
            values.extend(
                str(item)
                for item in final_errors
                if str(item).strip()
            )

    attempts = execution.get(
        "attempts",
        [],
    )

    if (
        isinstance(attempts, list)
        and attempts
        and isinstance(
            attempts[-1],
            dict,
        )
    ):
        values.extend(
            str(item)
            for item in attempts[-1].get(
                "errors",
                [],
            )
            if str(item).strip()
        )

    unique: list[str] = []

    for value in values:
        if value not in unique:
            unique.append(value)

    return unique[-10:]


def effective_execution_status(
    execution: dict[str, Any],
) -> str:
    final_result = execution.get(
        "final_result",
        {},
    )

    if isinstance(
        final_result,
        dict,
    ):
        final_status = str(
            final_result.get(
                "status",
                "",
            )
        ).upper()

        if final_status == "PREVIEW_READY":
            return "PREVIEW_READY"

    return str(
        execution.get(
            "status",
            "UNKNOWN",
        )
    ).upper()
