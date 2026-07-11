from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchResult:

    path: str

    score: float

    category: str = ""

    matched_fields: list[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def summary(self):

        return "\n".join([
            "SEARCH RESULT",
            f"Plik: {self.path}",
            f"Score: {self.score:.2f}",
            f"Kategoria: {self.category}",
            f"Dopasowania: {', '.join(self.matched_fields)}"
        ])