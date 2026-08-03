from __future__ import annotations

import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.continuous_dev.continuous_dev_command_router import (
    ContinuousDevCommandRouter,
)
from app.ai.continuous_dev.continuous_dev_controller import (
    ContinuousDevController,
)
from app.ai.evolution.evolution_command_router import (
    EvolutionCommandRouter,
)
from app.ai.evolution.evolution_controller import (
    EvolutionController,
)
from app.ai.self_improvement.improvement_command_router import (
    ImprovementCommandRouter,
)
from app.ai.self_improvement.improvement_controller import (
    ImprovementController,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_command_router import (
    SoftwareEngineerCommandRouter,
)


class AuditA313ControllerRoutingTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_large_controller_files_are_reduced(self) -> None:
        limits = {
            (
                "app/ai/evolution/"
                "evolution_controller.py"
            ): 540,
            (
                "app/ai/continuous_dev/"
                "continuous_dev_controller.py"
            ): 510,
            (
                "app/ai/self_improvement/"
                "improvement_controller.py"
            ): 410,
            (
                "app/ai/software_engineer/"
                "autonomous_software_engineer.py"
            ): 440,
        }

        failures: list[str] = []

        for relative, maximum in limits.items():
            lines = len(
                (
                    self.project_root
                    / relative
                ).read_text(
                    encoding="utf-8",
                ).splitlines()
            )

            if lines >= maximum:
                failures.append(
                    f"{relative}: {lines} >= {maximum}"
                )

        self.assertEqual(
            failures,
            [],
            "\n".join(failures),
        )

    def test_controller_handle_methods_are_thin_wrappers(self) -> None:
        files = (
            "app/ai/evolution/evolution_controller.py",
            (
                "app/ai/continuous_dev/"
                "continuous_dev_controller.py"
            ),
            (
                "app/ai/self_improvement/"
                "improvement_controller.py"
            ),
            (
                "app/ai/software_engineer/"
                "autonomous_software_engineer.py"
            ),
        )
        failures: list[str] = []

        for relative in files:
            tree = ast.parse(
                (
                    self.project_root
                    / relative
                ).read_text(
                    encoding="utf-8",
                )
            )
            controller_class = next(
                node
                for node in tree.body
                if isinstance(
                    node,
                    ast.ClassDef,
                )
            )
            handle = next(
                node
                for node in controller_class.body
                if isinstance(
                    node,
                    ast.FunctionDef,
                )
                and node.name == "handle"
            )
            length = (
                handle.end_lineno
                - handle.lineno
                + 1
            )

            if length > 12:
                failures.append(
                    f"{relative}: {length} linii"
                )

        self.assertEqual(
            failures,
            [],
            "\n".join(failures),
        )

    def test_command_routers_are_stateless(self) -> None:
        routers = (
            EvolutionCommandRouter(),
            ContinuousDevCommandRouter(),
            ImprovementCommandRouter(),
            SoftwareEngineerCommandRouter(),
        )

        self.assertTrue(
            all(
                vars(router) == {}
                for router in routers
            )
        )

    def test_evolution_list_behavior_is_preserved(self) -> None:
        controller = EvolutionController.__new__(
            EvolutionController
        )
        controller.list_runs = MagicMock(
            return_value=[
                {
                    "evolution_id": "evo-1",
                }
            ]
        )

        result = controller.handle(
            "evolution list"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["runs"][0][
                "evolution_id"
            ],
            "evo-1",
        )

    def test_continuous_dev_list_behavior_is_preserved(self) -> None:
        controller = ContinuousDevController.__new__(
            ContinuousDevController
        )
        controller.list_cycles = MagicMock(
            return_value=[
                {
                    "cycle_id": "cycle-1",
                }
            ]
        )

        result = controller.handle(
            "continuous dev list"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["cycles"][0][
                "cycle_id"
            ],
            "cycle-1",
        )

    def test_improvement_list_behavior_is_preserved(self) -> None:
        controller = ImprovementController.__new__(
            ImprovementController
        )
        controller.list_sessions = MagicMock(
            return_value=[
                {
                    "session_id": "session-1",
                }
            ]
        )

        result = controller.handle(
            "self improvement list"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["sessions"][0][
                "session_id"
            ],
            "session-1",
        )

    def test_software_engineer_rejection_is_preserved(self) -> None:
        controller = (
            AutonomousSoftwareEngineerController
            .__new__(
                AutonomousSoftwareEngineerController
            )
        )
        controller.can_handle = MagicMock(
            return_value=False
        )

        result = controller.handle(
            "zwykłe polecenie"
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "UNSUPPORTED_COMMAND",
        )


if __name__ == "__main__":
    unittest.main()
