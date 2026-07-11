from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ResearchTask:
    """
    Pojedyncze zadanie wygenerowane
    przez Research Agent.

    Następnie zostanie przekazane
    do DeveloperController.
    """

    title: str

    target: str

    description: str = ""

    task_type: str = "analysis"

    priority: int = 5

    estimated_risk: str = "LOW"

    estimated_time: int = 0

    requires_backup: bool = True

    requires_validation: bool = True

    requires_approval: bool = True

    status: str = "pending"

    actions: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    started_at: str = ""

    finished_at: str = ""

    def start(
        self
    ):

        self.status = "running"

        self.started_at = (
            datetime.now().isoformat()
        )

    def complete(
        self
    ):

        self.status = "completed"

        self.finished_at = (
            datetime.now().isoformat()
        )

    def fail(
        self
    ):

        self.status = "failed"

        self.finished_at = (
            datetime.now().isoformat()
        )

    def cancel(
        self
    ):

        self.status = "cancelled"

        self.finished_at = (
            datetime.now().isoformat()
        )

    def wait_for_approval(
        self
    ):

        self.status = (
            "waiting_for_approval"
        )

    def add_action(
        self,
        action: str
    ):

        action = action.strip()

        if (
            action
            and action not in self.actions
        ):

            self.actions.append(
                action
            )

    def is_finished(
        self
    ) -> bool:

        return self.status in {

            "completed",

            "failed",

            "cancelled"

        }

    def can_execute(
        self
    ) -> bool:

        return (
            self.status
            in {

                "pending",

                "approved"

            }
        )

    def summary(
        self
    ) -> str:

        lines = [

            "RESEARCH TASK",

            "",

            f"Title: {self.title}",

            f"Target: {self.target}",

            f"Type: {self.task_type}",

            f"Priority: {self.priority}",

            f"Risk: {self.estimated_risk}",

            f"Status: {self.status}",

            f"Estimated Time: "
            f"{self.estimated_time} min"

        ]

        lines.append("")

        lines.append(
            "Backup: "
            + (
                "YES"
                if self.requires_backup
                else "NO"
            )
        )

        lines.append(
            "Validation: "
            + (
                "YES"
                if self.requires_validation
                else "NO"
            )
        )

        lines.append(
            "Approval: "
            + (
                "YES"
                if self.requires_approval
                else "NO"
            )
        )

        if self.description:

            lines.append("")
            lines.append(
                self.description
            )

        if self.actions:

            lines.append("")
            lines.append(
                "Actions:"
            )

            for action in self.actions:

                lines.append(
                    f"- {action}"
                )

        return "\n".join(
            lines
        )

    def as_dict(
        self
    ) -> dict:

        return {

            "title":
                self.title,

            "target":
                self.target,

            "description":
                self.description,

            "task_type":
                self.task_type,

            "priority":
                self.priority,

            "estimated_risk":
                self.estimated_risk,

            "estimated_time":
                self.estimated_time,

            "requires_backup":
                self.requires_backup,

            "requires_validation":
                self.requires_validation,

            "requires_approval":
                self.requires_approval,

            "status":
                self.status,

            "actions":
                list(self.actions),

            "metadata":
                dict(self.metadata),

            "created_at":
                self.created_at,

            "started_at":
                self.started_at,

            "finished_at":
                self.finished_at

        }