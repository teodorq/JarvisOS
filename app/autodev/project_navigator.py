from app.autodev.module_graph import (
    ModuleGraph
)


class ProjectNavigator:

    def __init__(
        self,
        graph: ModuleGraph
    ):

        self.graph = graph

    def modules_of(
        self,
        category: str
    ):

        return self.graph.by_category(
            category
        )

    def find(
        self,
        text: str
    ):

        text = text.lower()

        return [
            node
            for node in self.graph.all()
            if (
                text in node.name.lower()
                or text in node.path.lower()
            )
        ]

    def largest_modules(self):

        return sorted(
            self.graph.all(),
            key=lambda node:
                node.degree(),
            reverse=True
        )