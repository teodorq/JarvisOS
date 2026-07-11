from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.autodev.improvement_suggestion import (
    ImprovementSuggestion
)
from app.autodev.research_result import (
    ResearchResult
)


@dataclass
class ResearchPlanItem:

    title: str

    description: str = ""

    target: str = ""

    priority: int = 5

    status: str = "pending"

    source_problem: str = ""

    estimated_risk: str = "LOW"

    actions: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def start(
        self
    ):
        self.status = "running"

    def complete(
        self
    ):
        self.status = "completed"

    def fail(
        self
    ):
        self.status = "failed"

    def skip(
        self
    ):
        self.status = "skipped"

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

    def as_dict(
        self
    ) -> dict:

        return {
            "title": self.title,
            "description": self.description,
            "target": self.target,
            "priority": self.priority,
            "status": self.status,
            "source_problem": self.source_problem,
            "estimated_risk": self.estimated_risk,
            "actions": list(
                self.actions
            ),
            "metadata": dict(
                self.metadata
            ),
            "created_at": self.created_at
        }

    def summary(
        self
    ) -> str:

        lines = [
            "RESEARCH PLAN ITEM",
            f"Tytuł: {self.title}",
            f"Target: {self.target or 'brak'}",
            f"Priorytet: {self.priority}",
            f"Status: {self.status}",
            f"Ryzyko: {self.estimated_risk}"
        ]

        if self.description:
            lines.append("")
            lines.append(
                self.description
            )

        if self.source_problem:
            lines.append("")
            lines.append(
                f"Źródło problemu: "
                f"{self.source_problem}"
            )

        if self.actions:
            lines.append("")
            lines.append("Akcje:")

            for action in self.actions:
                lines.append(
                    f"- {action}"
                )

        return "\n".join(
            lines
        )


@dataclass
class ResearchPlan:

    goal: str

    status: str = "created"

    items: List[
        ResearchPlanItem
    ] = field(
        default_factory=list
    )

    research_result: Optional[
        ResearchResult
    ] = None

    suggestions: List[
        ImprovementSuggestion
    ] = field(
        default_factory=list
    )

    selected_target: str = ""

    requires_approval: bool = True

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    updated_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def add_item(
        self,
        item: ResearchPlanItem
    ):
        self.items.append(
            item
        )

        self._sort()
        self._touch()

    def add_suggestion(
        self,
        suggestion: ImprovementSuggestion
    ):
        self.suggestions.append(
            suggestion
        )

        self._touch()

    def start(
        self
    ):
        self.status = "running"
        self._touch()

    def wait_for_approval(
        self
    ):
        self.status = "waiting_for_approval"
        self.requires_approval = True
        self._touch()

    def approve(
        self
    ):
        self.status = "approved"
        self.requires_approval = False
        self._touch()

    def complete(
        self
    ):
        self.status = "completed"
        self._touch()

    def fail(
        self
    ):
        self.status = "failed"
        self._touch()

    def pending(
        self
    ) -> List[ResearchPlanItem]:

        return [
            item
            for item in self.items
            if item.status == "pending"
        ]

    def completed(
        self
    ) -> List[ResearchPlanItem]:

        return [
            item
            for item in self.items
            if item.status == "completed"
        ]

    def failed(
        self
    ) -> List[ResearchPlanItem]:

        return [
            item
            for item in self.items
            if item.status == "failed"
        ]

    def next_item(
        self
    ) -> Optional[ResearchPlanItem]:

        for item in self.items:
            if item.status == "pending":
                return item

        return None

    def progress(
        self
    ) -> int:

        if not self.items:
            return 0

        finished_count = len([
            item
            for item in self.items
            if item.status in {
                "completed",
                "skipped"
            }
        ])

        return int(
            finished_count
            / len(self.items)
            * 100
        )

    def highest_priority_item(
        self
    ) -> Optional[ResearchPlanItem]:

        if not self.items:
            return None

        self._sort()

        return self.items[0]

    def validate(
        self
    ) -> tuple[bool, list[str]]:

        errors = []

        if not self.goal.strip():
            errors.append(
                "Brak celu planu badawczego."
            )

        if not self.items:
            errors.append(
                "Plan badawczy nie zawiera zadań."
            )

        for index, item in enumerate(
            self.items,
            start=1
        ):
            if not item.title.strip():
                errors.append(
                    f"Zadanie {index} nie ma tytułu."
                )

            if item.priority < 1:
                errors.append(
                    f"Niepoprawny priorytet zadania {index}."
                )

        return not errors, errors

    def as_dict(
        self
    ) -> dict:

        return {
            "goal": self.goal,
            "status": self.status,
            "items": [
                item.as_dict()
                for item in self.items
            ],
            "suggestions_count": len(
                self.suggestions
            ),
            "selected_target": self.selected_target,
            "requires_approval": self.requires_approval,
            "progress": self.progress(),
            "metadata": dict(
                self.metadata
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def summary(
        self
    ) -> str:

        lines = [
            "RESEARCH PLAN",
            f"Cel: {self.goal}",
            f"Status: {self.status}",
            f"Postęp: {self.progress()}%",
            f"Zadania: {len(self.items)}",
            f"Sugestie: {len(self.suggestions)}",
            (
                "Wymaga akceptacji: TAK"
                if self.requires_approval
                else "Wymaga akceptacji: NIE"
            )
        ]

        if self.selected_target:
            lines.append(
                f"Wybrany target: "
                f"{self.selected_target}"
            )

        if self.items:
            lines.append("")
            lines.append("Plan:")

            for item in self.items:
                lines.append(
                    f"[{item.status}] "
                    f"P{item.priority} "
                    f"{item.title}"
                )

                if item.target:
                    lines.append(
                        f"  Target: {item.target}"
                    )

                lines.append(
                    f"  Ryzyko: "
                    f"{item.estimated_risk}"
                )

        return "\n".join(
            lines
        )

    def _sort(
        self
    ):
        self.items.sort(
            key=lambda item: (
                item.priority,
                item.created_at
            )
        )

    def _touch(
        self
    ):
        self.updated_at = (
            datetime.now().isoformat()
        )