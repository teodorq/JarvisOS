from app.autodev.code_index import (
    CodeIndex
)
from app.autodev.project_scanner import (
    ProjectScanner
)
from app.autodev.semantic_search import (
    SemanticSearch
)


class CodeSearchEngine:

    def __init__(
        self,
        project_root="C:/JarvisAI"
    ):

        self.scanner = ProjectScanner(
            project_root
        )

        self.search_engine = (
            SemanticSearch()
        )

    def search(
        self,
        query: str
    ):

        project_index = (
            self.scanner.scan()
        )

        code_index = CodeIndex(
            project_index
        )

        return self.search_engine.search(
            code_index,
            query
        )

    def summary(
        self,
        query: str
    ):

        results = self.search(query)

        if not results:

            return (
                "Nie znaleziono "
                "żadnych wyników."
            )

        lines = [
            f"Wyniki dla: {query}",
            ""
        ]

        for result in results[:20]:

            lines.append(
                f"{result.score:>5.1f} | "
                f"{result.path}"
            )

        return "\n".join(lines)