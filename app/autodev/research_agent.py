from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import time

from app.autodev.code_reader import (
    CodeReader
)
from app.autodev.project_scanner import (
    ProjectScanner
)
from app.autodev.semantic_search import (
    SemanticSearch
)
from app.autodev.code_index import (
    CodeIndex
)
from app.autodev.research_finding import (
    ResearchFinding
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_result import (
    ResearchResult
)


class ResearchAgent:

    def __init__(
        self,
        project_root=default_project_root()
    ):

        self.project_root = project_root

        self.scanner = ProjectScanner(
            project_root
        )

        self.reader = CodeReader(
            project_root
        )

        self.semantic = SemanticSearch()

    def research(
        self,
        query: ResearchQuery
    ) -> ResearchResult:

        start = time.time()

        result = ResearchResult(
            goal=query.goal
        )

        valid, errors = (
            query.validate()
        )

        if not valid:

            result.success = False

            result.summary_text = (
                "\n".join(errors)
            )

            return result

        project_index = (
            self.scanner.scan()
        )

        code_index = CodeIndex(
            project_index
        )

        search_results = (
            self.semantic.search(
                code_index,
                query.goal
            )
        )

        limit = min(
            query.max_results,
            len(search_results)
        )

        for search in search_results[:limit]:

            code = self.reader.read(
                search.path
            )

            if not code["success"]:
                continue

            finding = ResearchFinding(

                path=search.path,

                title=(
                    code["relative_path"]
                ),

                category=search.category,

                score=search.score,

                summary_text=(
                    f"Plik zawiera "
                    f"{len(code['classes'])} klas, "
                    f"{len(code['functions'])} funkcji "
                    f"oraz "
                    f"{len(code['imports'])} importów."
                )
            )

            for keyword in (
                query.keywords
            ):

                lower = keyword.lower()

                if (
                    lower
                    in code["content"].lower()
                ):
                    finding.add_keyword(
                        keyword
                    )

            for cls in (
                code["classes"]
            ):

                finding.add_class(
                    cls["name"]
                )

            for func in (
                code["functions"]
            ):

                finding.add_function(
                    func["name"]
                )

            for imp in (
                code["imports"]
            ):

                finding.add_import(
                    imp["name"]
                )

            result.add(
                finding
            )

        result.duration = (
            time.time() - start
        )

        result.sort()

        result.summary_text = (
            f"Research Agent "
            f"znalazł "
            f"{result.count()} "
            f"pasujących plików."
        )

        return result

    def summary(
        self,
        query: ResearchQuery
    ) -> str:

        result = self.research(
            query
        )

        return result.report()