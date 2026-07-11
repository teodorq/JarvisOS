from app.autodev.improvement_suggestion import (
    ImprovementSuggestionEngine
)
from app.autodev.problem_detector import (
    ProblemDetector
)
from app.autodev.module_analysis import (
    ModuleAnalyzer
)
from app.autodev.research_plan import (
    ResearchPlan,
    ResearchPlanItem
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_result import (
    ResearchResult
)
from app.autodev.research_task import (
    ResearchTask
)


class ResearchPipeline:
    """
    Łączy wszystkie moduły Research
    i przygotowuje zadania dla AutoDev.
    """

    def __init__(self):

        self.analyzer = ModuleAnalyzer()

        self.detector = ProblemDetector()

        self.suggestions = (
            ImprovementSuggestionEngine()
        )

    def build_plan(
        self,
        query: ResearchQuery,
        result: ResearchResult,
        project_index
    ) -> ResearchPlan:

        plan = ResearchPlan(
            goal=query.goal
        )

        plan.research_result = result

        analyses = []

        path_map = {
            file.path: file
            for file in project_index.files
        }

        for finding in result.findings:

            project_file = path_map.get(
                finding.path
            )

            if project_file is None:
                continue

            analysis = self.analyzer.analyze(
                project_file
            )

            analyses.append(
                analysis
            )

        problems = self.detector.detect_many(
            analyses
        )

        suggestions = (
            self.suggestions.generate(
                problems
            )
        )

        for suggestion in suggestions:

            plan.add_suggestion(
                suggestion
            )

            priority = 5

            if suggestion.priority == "CRITICAL":
                priority = 1

            elif suggestion.priority == "HIGH":
                priority = 2

            elif suggestion.priority == "MEDIUM":
                priority = 3

            item = ResearchPlanItem(

                title=suggestion.title,

                description=(
                    suggestion.description
                ),

                target=suggestion.module,

                priority=priority,

                source_problem=(
                    suggestion.title
                ),

                estimated_risk=(
                    suggestion.priority
                )

            )

            for action in (
                suggestion.actions
            ):

                item.add_action(
                    action
                )

            plan.add_item(
                item
            )

        return plan

    def build_tasks(
        self,
        plan: ResearchPlan
    ) -> list[ResearchTask]:

        tasks = []

        for item in plan.items:

            task = ResearchTask(

                title=item.title,

                target=item.target,

                description=item.description,

                priority=item.priority,

                estimated_risk=(
                    item.estimated_risk
                )

            )

            if (
                item.priority <= 2
            ):

                task.estimated_time = 20

            elif (
                item.priority <= 4
            ):

                task.estimated_time = 10

            else:

                task.estimated_time = 5

            task.task_type = (
                "refactor"
            )

            for action in (
                item.actions
            ):

                task.add_action(
                    action
                )

            tasks.append(
                task
            )

        return tasks

    def summary(
        self,
        plan: ResearchPlan
    ) -> str:

        tasks = self.build_tasks(
            plan
        )

        lines = [

            "RESEARCH PIPELINE",

            "",

            f"Goal: {plan.goal}",

            f"Tasks: {len(tasks)}",

            ""

        ]

        for task in tasks:

            lines.append(

                f"P{task.priority}"

                f" "

                f"{task.title}"

            )

            lines.append(

                f"Target: "

                f"{task.target}"

            )

            lines.append("")

        return "\n".join(
            lines
        )