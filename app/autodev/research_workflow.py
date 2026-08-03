from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from app.autodev.research_goal_mapper import (
    ResearchGoalMapper
)
from app.autodev.research_controller import (
    ResearchController
)
from app.autodev.research_pipeline import (
    ResearchPipeline
)
from app.autodev.research_prioritizer import (
    ResearchPrioritizer
)
from app.autodev.research_scheduler import (
    ResearchScheduler
)
from app.autodev.research_decision_engine import (
    ResearchDecisionEngine
)
from app.autodev.research_executor import (
    ResearchExecutor
)


class ResearchWorkflow:
    """
    Kompletny workflow Research Agent.

    Goal
        ↓
    GoalMapper
        ↓
    Research
        ↓
    Pipeline
        ↓
    Prioritizer
        ↓
    Scheduler
        ↓
    Decision Engine
        ↓
    Executor
    """

    def __init__(
        self,
        project_root=default_project_root()
    ):

        self.mapper = (
            ResearchGoalMapper()
        )

        self.controller = (
            ResearchController(
                project_root
            )
        )

        self.pipeline = (
            ResearchPipeline()
        )

        self.prioritizer = (
            ResearchPrioritizer()
        )

        self.scheduler = (
            ResearchScheduler()
        )

        self.decision_engine = (
            ResearchDecisionEngine()
        )

        self.executor = (
            ResearchExecutor(
                project_root
            )
        )

        self.last_mapping = None
        self.last_result = None
        self.last_plan = None
        self.last_tasks = []
        self.last_schedule = []
        self.last_decisions = []

    def run(
        self,
        goal: str
    ):

        self.last_mapping = (
            self.mapper.map_goal(
                goal
            )
        )

        if not self.last_mapping.queries:
            raise RuntimeError(
                "Nie udało się utworzyć ResearchQuery."
            )

        query = (
            self.last_mapping.queries[0]
        )

        self.last_result = (
            self.controller.execute(
                query
            )
        )

        project_index = (
            self.controller
            .context
            .project_index
        )

        self.last_plan = (
            self.pipeline.build_plan(
                query,
                self.last_result,
                project_index
            )
        )

        self.last_tasks = (
            self.pipeline.build_tasks(
                self.last_plan
            )
        )

        self.last_tasks = (
            self.prioritizer.prioritize(
                self.last_tasks
            )
        )

        self.last_schedule = (
            self.scheduler.schedule(
                self.last_tasks
            )
        )

        self.last_decisions = (
            self.decision_engine
            .decide_many(
                self.last_tasks
            )
        )

        return self.last_result

    def report(
        self
    ) -> str:

        lines = [

            "RESEARCH WORKFLOW",

            ""
        ]

        if self.last_mapping:

            lines.append(
                self.last_mapping.summary()
            )

            lines.append("")

        if self.last_plan:

            lines.append(
                self.last_plan.summary()
            )

            lines.append("")

        if self.last_schedule:

            lines.append(
                self.scheduler.report()
            )

            lines.append("")

        if self.last_decisions:

            lines.append(
                self.decision_engine.report(
                    self.last_tasks
                )
            )

        return "\n".join(
            lines
        )

    def reset(
        self
    ):

        self.last_mapping = None
        self.last_result = None
        self.last_plan = None
        self.last_tasks.clear()
        self.last_schedule.clear()
        self.last_decisions.clear()

        self.scheduler.clear()