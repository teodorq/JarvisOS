from app.autodev.dependency_graph import DependencyGraph


class ChangeImpactAnalyzer:

    def __init__(self):
        self.graph = DependencyGraph()
        self.graph_ready = False

    def build_graph(self):
        self.graph.build()
        self.graph_ready = True
        return self.graph.summary_text()

    def analyze_symbol(self, symbol_name: str):
        if not self.graph_ready:
            self.graph.build()
            self.graph_ready = True

        impact = self.graph.impact_for_symbol(symbol_name)

        risk = self._risk_level(
            impact.get("files_count", 0),
            impact.get("references_count", 0)
        )

        lines = [
            "CHANGE IMPACT",
            f"Symbol: {symbol_name}",
            f"Referencje: {impact.get('references_count', 0)}",
            f"Pliki: {impact.get('files_count', 0)}",
            f"Ryzyko: {risk}",
            ""
        ]

        files = impact.get("files", [])

        if files:
            lines.append("Pliki zależne:")

            for path in files[:30]:
                lines.append(f"- {path}")
        else:
            lines.append("Nie znaleziono zależności.")

        return "\n".join(lines)

    def analyze_module(self, module_name: str):
        if not self.graph_ready:
            self.graph.build()
            self.graph_ready = True

        edges = self.graph.files_using_module(module_name)

        files = sorted({
            edge.get("source", "")
            for edge in edges
            if edge.get("source")
        })

        risk = self._risk_level(len(files), len(edges))

        lines = [
            "MODULE IMPACT",
            f"Moduł: {module_name}",
            f"Importy: {len(edges)}",
            f"Pliki: {len(files)}",
            f"Ryzyko: {risk}",
            ""
        ]

        for path in files[:30]:
            lines.append(f"- {path}")

        return "\n".join(lines)

    def _risk_level(self, files_count: int, references_count: int):
        if files_count >= 15 or references_count >= 40:
            return "high"

        if files_count >= 5 or references_count >= 10:
            return "medium"

        return "low"