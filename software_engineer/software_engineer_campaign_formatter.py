from __future__ import annotations

from typing import Any


def format_change_campaign_response(
    response: dict[str, Any],
) -> str:
    campaign = response.get(
        "campaign",
        {},
    )
    status = str(
        response.get(
            "status",
            "UNKNOWN",
        )
    )
    campaign_id = str(
        response.get(
            "campaign_id",
            campaign.get(
                "campaign_id",
                "",
            )
            if isinstance(
                campaign,
                dict,
            )
            else "",
        )
    )
    stages_count = int(
        response.get(
            "stages_count",
            len(
                campaign.get(
                    "stages",
                    [],
                )
            )
            if isinstance(
                campaign,
                dict,
            )
            else 0,
        )
        or 0
    )
    completed = int(
        response.get(
            "completed_stages",
            len(
                campaign.get(
                    "completed_stage_ids",
                    [],
                )
            )
            if isinstance(
                campaign,
                dict,
            )
            else 0,
        )
        or 0
    )
    lines = [
        (
            "Autonomous Software Engineer: "
            f"{status}"
        ),
        f"Kampania zmian: {campaign_id or 'brak'}",
        (
            "Postęp etapów: "
            f"{completed}/{stages_count}"
        ),
    ]

    if isinstance(
        campaign,
        dict,
    ):
        current = str(
            campaign.get(
                "current_stage_id",
                "",
            )
        ).strip()

        if current:
            lines.append(
                f"Bieżący etap: {current}"
            )

        checkpoints = campaign.get(
            "checkpoints",
            [],
        )

        if isinstance(
            checkpoints,
            list,
        ) and checkpoints:
            last = checkpoints[-1]

            if isinstance(
                last,
                dict,
            ):
                lines.append(
                    "Ostatni checkpoint: "
                    f"{last.get('event', 'UNKNOWN')}"
                )

    validation = response.get(
        "final_validation",
        {},
    )

    if isinstance(
        validation,
        dict,
    ) and validation:
        lines.append(
            "Walidacja całego projektu: "
            f"{validation.get('status', 'UNKNOWN')}"
        )

    rollback = response.get(
        "rollback",
        {},
    )

    if isinstance(
        rollback,
        dict,
    ) and rollback:
        lines.append(
            "Rollback kampanii: "
            f"{rollback.get('status', 'UNKNOWN')}"
        )

    report_path = str(
        response.get(
            "report_path",
            "",
        )
    ).strip()

    if report_path:
        lines.append(
            f"Raport kampanii: {report_path}"
        )

    if status == "CAMPAIGN_PAUSED":
        lines.append(
            "Kampania jest zapisana i może "
            "zostać wznowiona po campaign_id."
        )

    return "\n".join(lines)
