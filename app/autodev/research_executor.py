from app.autodev.research_developer import (
    ResearchDeveloper
)
from app.autodev.research_pipeline import (
    ResearchPipeline
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_controller import (
    ResearchController
)


class ResearchExecutor:
    """
    Główny punkt wykonania
    Research → AutoDev.

    Workflow:

    Query
        ↓
    Research
        ↓
    Plan
        ↓
    Tasks
        ↓
    Developer
        ↓
    Preview
        ↓
    Approval
        ↓
    Execute
    """

    def __init__(
        self,
        project_root="C:/JarvisAI"
    ):

        self.controller = (
            ResearchController(
                project_root
            )
        )

        self.pipeline = (
            ResearchPipeline()
        )

        self.developer = (
            ResearchDeveloper(
                project_root
            )
        )

        self.last_plan = None

        self.last_tasks = []

    def execute_research(
        self,
        query: ResearchQuery
    ):

        result = (
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
                result,
                project_index
            )
        )

        self.last_tasks = (
            self.pipeline.build_tasks(
                self.last_plan
            )
        )

        return result

    def plan(self):

        return self.last_plan

    def tasks(self):

        return self.last_tasks

    def task(
        self,
        index: int
    ):

        if (
            index < 0
            or index >= len(
                self.last_tasks
            )
        ):
            return None

        return self.last_tasks[
            index
        ]

    def prepare_file_patch(
        self,
        task_index: int,
        proposed_content: str
    ):

        task = self.task(
            task_index
        )

        if task is None:
            raise ValueError(
                "Nie ma takiego zadania."
            )

        return (
            self.developer
            .prepare_file_change(
                task,
                proposed_content
            )
        )

    def prepare_function_patch(
        self,
        task_index: int,
        function_name: str,
        function_code: str
    ):

        task = self.task(
            task_index
        )

        if task is None:
            raise ValueError(
                "Nie ma takiego zadania."
            )

        return (
            self.developer
            .prepare_function_change(
                task,
                function_name,
                function_code
            )
        )

    def preview(
        self
    ):

        return (
            self.developer.preview()
        )

    def approve(
        self
    ):

        return (
            self.developer.approve()
        )

    def execute(
        self
    ):

        return (
            self.developer.execute()
        )

    def rollback(
        self
    ):

        return (
            self.developer.rollback_last()
        )

    def report(
        self
    ):

        lines = [

            "RESEARCH EXECUTOR",

            ""

        ]

        if self.last_plan:

            lines.append(
                self.last_plan.summary()
            )

            lines.append("")

        lines.append(
            self.developer.report()
        )

        return "\n".join(
            lines
        )