from app.autodev.search_result import (
    SearchResult
)


class SemanticSearch:

    def search(
        self,
        code_index,
        query: str
    ):

        query = query.lower()

        results = []

        for file in code_index.all():

            score = 0
            matched = []

            if query in file.path.lower():
                score += 10
                matched.append("path")

            if query in file.category.lower():
                score += 5
                matched.append("category")

            for cls in file.classes:

                if query in cls.lower():
                    score += 4

                    if "class" not in matched:
                        matched.append("class")

            for func in file.functions:

                if query in func.lower():
                    score += 4

                    if "function" not in matched:
                        matched.append("function")

            for imp in file.imports:

                if query in imp.lower():
                    score += 3

                    if "import" not in matched:
                        matched.append("import")

            if score == 0:
                continue

            results.append(
                SearchResult(
                    path=file.path,
                    score=float(score),
                    category=file.category,
                    matched_fields=matched
                )
            )

        results.sort(
            key=lambda r: r.score,
            reverse=True
        )

        return results