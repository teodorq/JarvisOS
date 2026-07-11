from typing import Any
from app.autodev.merge_decision import MergeDecisionEngine
from app.autodev.regression_analyzer import RegressionAnalyzer
from app.autodev.test_runner import TestRunner
from app.autodev.test_selector import TestSelector

class AutoTestOrchestrator:
    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        selector=None,
        runner=None,
        analyzer=None,
        decision_engine=None,
    ) -> None:
        self.selector = selector or TestSelector()
        self.runner = runner or TestRunner(project_root)
        self.analyzer = analyzer or RegressionAnalyzer()
        self.decision_engine = decision_engine or MergeDecisionEngine()
        self.last_result: dict[str, Any] | None = None

    def run(self, changed_files: list[str]) -> dict[str, Any]:
        plan = self.selector.build_plan(changed_files)
        tests = self.runner.run(plan)
        regression = self.analyzer.analyze(tests)
        decision = self.decision_engine.decide(
            test_result=tests,
            regression_result=regression,
        )

        result = {
            "success": decision["decision"] == "MERGE",
            "status": decision["status"],
            "plan": plan.to_dict(),
            "tests": tests,
            "regression": regression,
            "decision": decision,
        }

        self.last_result = result
        return result
