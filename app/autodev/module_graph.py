from app.autodev.module_node import (
    ModuleNode
)


class ModuleGraph:

    def __init__(self):

        self.nodes = {}

    def add_node(
        self,
        node: ModuleNode
    ):

        self.nodes[node.path] = node

    def get(
        self,
        path: str
    ):

        return self.nodes.get(path)

    def all(self):

        return list(
            self.nodes.values()
        )

    def count(self):

        return len(
            self.nodes
        )

    def by_category(
        self,
        category: str
    ):

        return [
            node
            for node in self.nodes.values()
            if node.category == category
        ]

    def summary(self):

        lines = [
            "MODULE GRAPH",
            f"Nodes: {self.count()}",
            ""
        ]

        for node in self.nodes.values():

            lines.append(
                node.name
            )

        return "\n".join(lines)