from app.autodev.ai_reasoner import AIReasoner
from app.autodev.autodev_context import AutoDevContext
from app.autodev.goal import Goal
from app.autodev.goal_planner import GoalPlanner
from app.autodev.knowledge_graph import KnowledgeGraph
from app.autodev.project_scanner import ProjectScanner
from app.autodev.semantic_search import SemanticSearch
from app.autodev.code_index import CodeIndex


class AutoDevBrain:

    def __init__(
        self,
        project_root="C:/JarvisAI"
    ):

        self.project_root = project_root

        self.scanner = ProjectScanner(
            project_root
        )

        self.graph = KnowledgeGraph(
            project_root
        )

        self.reasoner = AIReasoner()

        self.planner = GoalPlanner()

        self.search = SemanticSearch()

    def analyze(
        self,
        goal_text: str
    ):

        context = AutoDevContext()

        context.goal = goal_text

        project_index = (
            self.scanner.scan()
        )

        context.project_index = (
            project_index
        )

        context.knowledge_graph = (
            self.graph.build()
        )

        code_index = CodeIndex(
            project_index
        )

        context.search_results = (
            self.search.search(
                code_index,
                goal_text
            )
        )

        goal = Goal(
            title=goal_text
        )

        context.reasoning = (
            self.reasoner.analyze(
                goal
            )
        )

        context.development_plan = (
            self.planner.build_plan(
                goal
            )
        )

        return context