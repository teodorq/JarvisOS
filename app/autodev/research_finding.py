from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ResearchFinding:

    path: str

    title: str

    category: str = "unknown"

    score: float = 0.0

    finding_type: str = "code"

    summary_text: str = ""

    matched_keywords: List[str] = field(
        default_factory=list
    )

    matched_classes: List[str] = field(
        default_factory=list
    )

    matched_functions: List[str] = field(
        default_factory=list
    )

    matched_imports: List[str] = field(
        default_factory=list
    )

    references: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_keyword(
        self,
        keyword: str
    ):
        keyword = keyword.strip()

        if (
            keyword
            and keyword not in self.matched_keywords
        ):
            self.matched_keywords.append(
                keyword
            )

    def add_class(
        self,
        class_name: str
    ):
        class_name = class_name.strip()

        if (
            class_name
            and class_name not in self.matched_classes
        ):
            self.matched_classes.append(
                class_name
            )

    def add_function(
        self,
        function_name: str
    ):
        function_name = function_name.strip()

        if (
            function_name
            and function_name not in self.matched_functions
        ):
            self.matched_functions.append(
                function_name
            )

    def add_import(
        self,
        import_name: str
    ):
        import_name = import_name.strip()

        if (
            import_name
            and import_name not in self.matched_imports
        ):
            self.matched_imports.append(
                import_name
            )

    def add_reference(
        self,
        reference: str
    ):
        reference = reference.strip()

        if (
            reference
            and reference not in self.references
        ):
            self.references.append(
                reference
            )

    def total_matches(
        self
    ) -> int:
        return (
            len(self.matched_keywords)
            + len(self.matched_classes)
            + len(self.matched_functions)
            + len(self.matched_imports)
            + len(self.references)
        )

    def relevance_level(
        self
    ) -> str:
        if self.score >= 20:
            return "very_high"

        if self.score >= 12:
            return "high"

        if self.score >= 6:
            return "medium"

        if self.score > 0:
            return "low"

        return "none"

    def as_dict(
        self
    ) -> dict:
        return {
            "path": self.path,
            "title": self.title,
            "category": self.category,
            "score": self.score,
            "finding_type": self.finding_type,
            "summary_text": self.summary_text,
            "matched_keywords": self.matched_keywords,
            "matched_classes": self.matched_classes,
            "matched_functions": self.matched_functions,
            "matched_imports": self.matched_imports,
            "references": self.references,
            "metadata": self.metadata,
            "created_at": self.created_at
        }

    def summary(
        self
    ) -> str:
        lines = [
            "RESEARCH FINDING",
            f"Title: {self.title}",
            f"Path: {self.path}",
            f"Category: {self.category}",
            f"Type: {self.finding_type}",
            f"Score: {self.score:.2f}",
            f"Relevance: {self.relevance_level()}",
            f"Matches: {self.total_matches()}"
        ]

        if self.summary_text:
            lines.append("")
            lines.append(
                self.summary_text
            )

        if self.matched_keywords:
            lines.append("")
            lines.append(
                "Matched keywords:"
            )

            for item in self.matched_keywords:
                lines.append(
                    f"- {item}"
                )

        if self.matched_classes:
            lines.append("")
            lines.append(
                "Matched classes:"
            )

            for item in self.matched_classes:
                lines.append(
                    f"- {item}"
                )

        if self.matched_functions:
            lines.append("")
            lines.append(
                "Matched functions:"
            )

            for item in self.matched_functions:
                lines.append(
                    f"- {item}"
                )

        if self.matched_imports:
            lines.append("")
            lines.append(
                "Matched imports:"
            )

            for item in self.matched_imports:
                lines.append(
                    f"- {item}"
                )

        if self.references:
            lines.append("")
            lines.append(
                "References:"
            )

            for item in self.references:
                lines.append(
                    f"- {item}"
                )

        return "\n".join(
            lines
        )