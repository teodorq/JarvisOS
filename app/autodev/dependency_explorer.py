from dataclasses import dataclass, field

from app.autodev.module_graph import (
    ModuleGraph
)
from app.autodev.module_node import (
    ModuleNode
)


@dataclass
class DependencyInfo:

    module: str

    imports: list[str] = field(
        default_factory=list
    )

    imported_by: list[str] = field(
        default_factory=list
    )

    degree: int = 0

    risk: str = "LOW"

    def summary(self) -> str:

        lines = [

            "DEPENDENCY INFO",

            "",

            f"Module: {self.module}",

            f"Imports: {len(self.imports)}",

            f"Imported by: {len(self.imported_by)}",

            f"Degree: {self.degree}",

            f"Risk: {self.risk}"

        ]

        return "\n".join(lines)


class DependencyExplorer:

    """
    Analizuje zależności modułów.

    To pierwszy krok do
    automatycznego wykrywania
    krytycznych elementów projektu.
    """

    def analyze(
        self,
        graph: ModuleGraph,
        module_name: str
    ) -> DependencyInfo | None:

        target = None

        for node in graph.all():

            if (
                node.name.lower()
                == module_name.lower()
            ):

                target = node

                break

        if target is None:
            return None

        info = DependencyInfo(
            module=target.name
        )

        info.imports = list(
            target.imports
        )

        info.imported_by = list(
            target.imported_by
        )

        info.degree = (
            len(info.imports)
            + len(info.imported_by)
        )

        if info.degree >= 30:

            info.risk = "CRITICAL"

        elif info.degree >= 20:

            info.risk = "HIGH"

        elif info.degree >= 10:

            info.risk = "MEDIUM"

        else:

            info.risk = "LOW"

        return info

    def most_connected(
        self,
        graph: ModuleGraph,
        limit: int = 20
    ) -> list[ModuleNode]:

        modules = sorted(

            graph.all(),

            key=lambda node:
                node.degree(),

            reverse=True

        )

        return modules[:limit]