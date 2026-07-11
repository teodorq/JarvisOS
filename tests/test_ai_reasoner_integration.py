from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.ai.reasoner.decision_graph import DecisionGraph
from app.ai.reasoner.goal_reasoner import GoalReasoner
from app.ai.reasoner.option_generator import OptionGenerator
from app.ai.reasoner.reasoner_router import ReasonerRouter
from app.ai.reasoner.reasoning_controller import (
    ReasoningController,
)
from app.ai.reasoner.reasoning_memory import ReasoningMemory
from app.ai.reasoner.risk_evaluator import RiskEvaluator
from app.ai.reasoner.strategy_builder import StrategyBuilder
from app.ai.reasoning_service import ReasoningService


class FakeResearchService:

    def execute(
        self,
        command: str,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "COMPLETED",
            "report": (
                "Testowy research zakończony."
            ),
            "command": command,
            "dependency_count": 3,
            "affected_files": 1,
            "tests_available": True,
            "rollback_available": True,
        }


class FakeDeveloperController:

    def execute(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "COMPLETED",
            "payload_received": bool(payload),
            "validation": {
                "success": True,
                "valid": True,
                "status": "VALIDATED",
            },
            "rollback": {
                "used": False,
                "success": False,
            },
        }


class AIReasonerIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        memory_path = (
            Path(
                self.temp_directory.name
            )
            / "reasoning_memory.json"
        )

        self.memory = ReasoningMemory(
            storage_path=memory_path
        )

        self.controller = ReasoningController(
            reasoning_memory=self.memory,
            research_service=FakeResearchService(),
            developer_controller=(
                FakeDeveloperController()
            ),
        )

        self.service = ReasoningService(
            controller=self.controller
        )

    def tearDown(
        self,
    ) -> None:

        self.temp_directory.cleanup()

    def test_goal_reasoner_detects_bug_fix(
        self,
    ) -> None:

        reasoner = GoalReasoner()

        goal = reasoner.reason(
            "Napraw błąd w module Vision"
        )

        self.assertEqual(
            goal["goal_type"],
            "BUG_FIX",
        )

        self.assertTrue(
            goal["requires_developer"]
        )

        self.assertIn(
            "vision",
            goal["detected_modules"],
        )

    def test_decision_graph_is_created(
        self,
    ) -> None:

        reasoner = GoalReasoner()
        graph_builder = DecisionGraph()

        goal = reasoner.reason(
            "Napraw błąd w module Vision"
        )

        graph = graph_builder.build(
            goal
        )

        self.assertTrue(
            graph["graph_id"].startswith(
                "decision_graph_"
            )
        )

        self.assertGreater(
            graph["metadata"]["nodes_count"],
            0,
        )

        node_types = {
            node["node_type"]
            for node in graph["nodes"]
        }

        self.assertIn(
            "GOAL_ANALYSIS",
            node_types,
        )

        self.assertIn(
            "RISK_EVALUATION",
            node_types,
        )

    def test_options_and_risk_are_generated(
        self,
    ) -> None:

        goal_reasoner = GoalReasoner()
        option_generator = OptionGenerator()
        risk_evaluator = RiskEvaluator()

        goal = goal_reasoner.reason(
            "Napraw błąd w module Vision"
        )

        options = option_generator.generate(
            goal=goal,
            research_context={
                "success": True,
            },
        )

        risk = risk_evaluator.evaluate(
            goal=goal,
            options_result=options,
            research_context={
                "success": True,
            },
            project_context={
                "dependency_count": 3,
                "affected_files": 1,
                "tests_available": True,
                "rollback_available": True,
            },
        )

        self.assertGreater(
            len(options["options"]),
            0,
        )

        self.assertGreater(
            len(risk["assessments"]),
            0,
        )

        self.assertIsNotNone(
            risk["recommended_option_id"]
        )

    def test_strategy_builder_creates_strategy(
        self,
    ) -> None:

        goal_reasoner = GoalReasoner()
        graph_builder = DecisionGraph()
        option_generator = OptionGenerator()
        risk_evaluator = RiskEvaluator()
        strategy_builder = StrategyBuilder()

        goal = goal_reasoner.reason(
            "Napraw błąd w module Vision"
        )

        graph = graph_builder.build(
            goal
        )

        research_context = {
            "success": True,
            "dependency_count": 3,
            "affected_files": 1,
            "tests_available": True,
            "rollback_available": True,
        }

        options = option_generator.generate(
            goal=goal,
            decision_graph=graph,
            research_context=research_context,
        )

        risk = risk_evaluator.evaluate(
            goal=goal,
            options_result=options,
            research_context=research_context,
            project_context=research_context,
        )

        strategy = strategy_builder.build(
            goal=goal,
            options_result=options,
            risk_result=risk,
            decision_graph=graph,
            research_context=research_context,
        )

        self.assertIn(
            strategy["status"],
            {
                "READY",
                "BLOCKED",
            },
        )

        self.assertTrue(
            strategy["strategy_id"].startswith(
                "strategy_"
            )
        )

        self.assertGreater(
            len(strategy["phases"]),
            0,
        )

    def test_reasoner_router_matches_command(
        self,
    ) -> None:

        router = ReasonerRouter()

        result = router.route(
            "Rozumuj napraw błąd w Vision"
        )

        self.assertTrue(
            result["matched"]
        )

        self.assertEqual(
            result["route"],
            "REASON",
        )

    def test_reasoning_service_creates_session(
        self,
    ) -> None:

        response = self.service.handle(
            command=(
                "Rozumuj napraw błąd "
                "w module Vision"
            ),
            context={
                "project_context": {
                    "dependency_count": 3,
                    "affected_files": 1,
                    "tests_available": True,
                    "rollback_available": True,
                },
            },
        )

        self.assertTrue(
            response["handled"]
        )

        self.assertEqual(
            response["route"],
            "REASON",
        )

        result = response["result"]

        self.assertTrue(
            result["session_id"].startswith(
                "reasoning_session_"
            )
        )

        self.assertIn(
            "strategy",
            result,
        )

        self.assertIn(
            "risk_result",
            result,
        )

    def test_session_can_be_approved_and_executed(
        self,
    ) -> None:

        analysis = self.controller.reason(
            user_request=(
                "Napraw błąd w module Vision"
            ),
            research_context={
                "success": True,
                "dependency_count": 3,
                "affected_files": 1,
                "tests_available": True,
                "rollback_available": True,
            },
            project_context={
                "dependency_count": 3,
                "affected_files": 1,
                "tests_available": True,
                "rollback_available": True,
            },
            auto_execute=False,
        )

        session_id = analysis[
            "session_id"
        ]

        execution = (
            self.controller.approve_session(
                session_id=session_id,
                approved=True,
                execute=True,
            )
        )

        self.assertTrue(
            execution["success"]
        )

        self.assertEqual(
            execution["status"],
            "COMPLETED",
        )

    def test_reasoning_memory_records_execution(
        self,
    ) -> None:

        analysis = self.controller.reason(
            user_request=(
                "Napraw błąd w module Vision"
            ),
            research_context={
                "success": True,
            },
            project_context={
                "dependency_count": 1,
                "affected_files": 1,
                "tests_available": True,
                "rollback_available": True,
            },
            auto_execute=False,
        )

        session_id = analysis[
            "session_id"
        ]

        self.controller.approve_session(
            session_id=session_id,
            approved=True,
            execute=True,
        )

        summary = self.memory.summary()

        self.assertEqual(
            summary["entries_count"],
            1,
        )

        self.assertEqual(
            summary["successful_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )