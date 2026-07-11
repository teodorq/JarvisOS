from dataclasses import dataclass, field


@dataclass
class ModuleNode:

    name: str

    path: str

    category: str

    imports: list[str] = field(
        default_factory=list
    )

    imported_by: list[str] = field(
        default_factory=list
    )

    functions: list[str] = field(
        default_factory=list
    )

    classes: list[str] = field(
        default_factory=list
    )

    def degree(self) -> int:
        return (
            len(self.imports)
            + len(self.imported_by)
        )

    def summary(self):

        return "\n".join([
            self.name,
            f"Kategoria: {self.category}",
            f"Importuje: {len(self.imports)}",
            f"Używany przez: {len(self.imported_by)}",
            f"Klasy: {len(self.classes)}",
            f"Funkcje: {len(self.functions)}"
        ])