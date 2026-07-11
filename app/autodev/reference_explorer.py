from dataclasses import dataclass, field

from app.autodev.project_index import (
    ProjectIndex
)


@dataclass
class ReferenceResult:

    symbol: str

    references: list[str] = field(
        default_factory=list
    )

    files: list[str] = field(
        default_factory=list
    )

    score: int = 0

    def add(
        self,
        file_path: str,
        reference: str
    ):

        if file_path not in self.files:
            self.files.append(
                file_path
            )

        self.references.append(
            reference
        )

        self.score = len(
            self.references
        )

    def summary(
        self
    ) -> str:

        lines = [

            "REFERENCE RESULT",

            "",

            f"Symbol: {self.symbol}",

            f"Files: {len(self.files)}",

            f"References: {len(self.references)}",

            f"Score: {self.score}",

            ""
        ]

        for file in self.files:

            lines.append(
                f"- {file}"
            )

        return "\n".join(
            lines
        )


class ReferenceExplorer:

    """
    Wyszukuje użycia klas,
    funkcji oraz modułów
    w całym projekcie.
    """

    def search(
        self,
        project_index: ProjectIndex,
        symbol: str
    ) -> ReferenceResult:

        result = ReferenceResult(
            symbol=symbol
        )

        symbol_lower = (
            symbol.lower()
        )

        for file in project_index.files:

            found = False

            for cls in file.classes:

                if (
                    symbol_lower
                    in cls.lower()
                ):

                    result.add(
                        file.path,
                        f"class:{cls}"
                    )

                    found = True

            for func in file.functions:

                if (
                    symbol_lower
                    in func.lower()
                ):

                    result.add(
                        file.path,
                        f"function:{func}"
                    )

                    found = True

            for imp in file.imports:

                if (
                    symbol_lower
                    in imp.lower()
                ):

                    result.add(
                        file.path,
                        f"import:{imp}"
                    )

                    found = True

            if (
                symbol_lower
                in file.path.lower()
            ):

                result.add(
                    file.path,
                    "path"
                )

                found = True

            if (
                found
                and hasattr(
                    file,
                    "references"
                )
            ):

                for ref in (
                    file.references
                ):

                    if (
                        symbol_lower
                        in ref.lower()
                    ):

                        result.add(
                            file.path,
                            f"reference:{ref}"
                        )

        return result

    def most_used(
        self,
        project_index: ProjectIndex,
        symbols: list[str]
    ) -> list[ReferenceResult]:

        results = []

        for symbol in symbols:

            results.append(
                self.search(
                    project_index,
                    symbol
                )
            )

        results.sort(

            key=lambda item:
                item.score,

            reverse=True

        )

        return results