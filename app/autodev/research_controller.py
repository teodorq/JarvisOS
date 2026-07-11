from app.autodev.project_scanner import (
    ProjectScanner
)
from app.autodev.knowledge_graph import (
    KnowledgeGraph
)
from app.autodev.semantic_search import (
    SemanticSearch
)
from app.autodev.code_index import (
    CodeIndex
)
from app.autodev.code_reader import (
    CodeReader
)
from app.autodev.research_agent import (
    ResearchAgent
)
from app.autodev.research_context import (
    ResearchContext
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_result import (
    ResearchResult
)
from app.autodev.research_session import (
    ResearchSession
)
from app.autodev.research_strategy import (
    ResearchStrategy
)


class ResearchController:

    """
    Główny kontroler Research Agent.

    Odpowiada za:

    Query
        ↓
    Project Scan
        ↓
    Semantic Search
        ↓
    Code Reader
        ↓
    Research Agent
        ↓
    Context
        ↓
    Session
        ↓
    Result
    """

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

        self.reader = CodeReader(
            project_root
        )

        self.semantic = SemanticSearch()

        self.agent = ResearchAgent(
            project_root
        )

        self.session = (
            ResearchSession()
        )

        self.context = (
            ResearchContext()
        )

    def execute(
        self,
        query: ResearchQuery,
        strategy: ResearchStrategy
        | None = None
    ) -> ResearchResult:

        self.session.start(
            query
        )

        self.context = (
            ResearchContext()
        )

        self.context.query = query

        project_index = (
            self.scanner.scan()
        )

        self.context.project_index = (
            project_index
        )

        self.context.knowledge_graph = (
            self.graph.build()
        )

        code_index = CodeIndex(
            project_index
        )

        self.context.search_results = (
            self.semantic.search(
                code_index,
                query.goal
            )
        )

        if strategy is None:

            strategy = (
                ResearchStrategy(
                    name="Default"
                )
            )

        limit = min(
            strategy.max_files,
            len(
                self.context
                .search_results
            )
        )

        self.context.search_results = (
            self.context.search_results[
                :limit
            ]
        )

        result = (
            self.agent.research(
                query
            )
        )

        self.context.result = (
            result
        )

        for finding in (
            result.findings
        ):

            self.context.add_file(
                finding.path
            )

        self.session.finish(
            result
        )

        return result

    def status(
        self
    ) -> dict:

        return {

            "session_status":
                self.session.status,

            "research_count":
                self.session
                .memory
                .count(),

            "last_goal":
                (
                    self.session
                    .current_query
                    .goal
                    if self.session
                    .current_query
                    else ""
                ),

            "last_result_count":
                (
                    self.session
                    .current_result
                    .count()
                    if self.session
                    .current_result
                    else 0
                )

        }

    def report(
        self
    ) -> str:

        lines = [

            "RESEARCH CONTROLLER",

            "",

            self.session.summary(),

            "",

            self.context.summary()

        ]

        if (
            self.session
            .current_result
        ):

            lines.append("")

            lines.append(

                self.session
                .current_result
                .report()

            )

        return "\n".join(
            lines
        )

    def reset(
        self
    ):

        self.session.reset()

        self.context = (
            ResearchContext()
        )