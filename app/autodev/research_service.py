from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from app.autodev.research_router import (
    ResearchRouter
)


class ResearchService:
    """
    Warstwa usługowa pomiędzy Brain
    a ResearchWorkflow.
    """

    def __init__(
        self,
        project_root=default_project_root()
    ):

        self.router = ResearchRouter(
            project_root
        )

    def can_handle(
        self,
        prompt: str
    ) -> bool:

        return self.router.can_handle(
            prompt
        )

    def execute(
        self,
        prompt: str
    ) -> dict:

        return self.router.handle(
            prompt
        )

    def analyze(
        self,
        goal: str
    ) -> dict:

        return self.execute(
            goal
        )

    def report(
        self,
        goal: str
    ) -> str:

        result = self.execute(
            goal
        )

        return result.get(
            "report",
            ""
        )

    def summary(
        self
    ) -> str:

        return "\n".join([
            "RESEARCH SERVICE",
            "",
            "Status: READY",
            "Router: ONLINE",
            "Workflow: ONLINE"
        ])