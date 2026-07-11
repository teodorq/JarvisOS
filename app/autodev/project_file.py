from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProjectFile:

    path: str

    category: str = "unknown"

    size: int = 0

    imports: list[str] = field(
        default_factory=list
    )

    classes: list[str] = field(
        default_factory=list
    )

    functions: list[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def summary(self):

        return "\n".join([
            self.path,
            f"Kategoria: {self.category}",
            f"Importy: {len(self.imports)}",
            f"Klasy: {len(self.classes)}",
            f"Funkcje: {len(self.functions)}"
        ])