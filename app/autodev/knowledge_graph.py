from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from pathlib import Path

from app.autodev.module_graph import (
    ModuleGraph
)
from app.autodev.module_node import (
    ModuleNode
)
from app.autodev.project_scanner import (
    ProjectScanner
)


class KnowledgeGraph:

    def __init__(
        self,
        project_root=default_project_root()
    ):

        self.scanner = ProjectScanner(
            project_root
        )

    def build(self):

        index = self.scanner.scan()

        graph = ModuleGraph()

        lookup = {}

        for file in index.files:

            node = ModuleNode(
                name=Path(file.path).stem,
                path=file.path,
                category=file.category,
                imports=file.imports,
                classes=file.classes,
                functions=file.functions
            )

            graph.add_node(node)

            lookup[node.name] = node

        for node in graph.all():

            for imported in node.imports:

                short = imported.split(".")[-1]

                target = lookup.get(short)

                if target:

                    target.imported_by.append(
                        node.name
                    )

        return graph