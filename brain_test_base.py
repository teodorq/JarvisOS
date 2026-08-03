from unittest.mock import MagicMock

from app.ai.brain import Brain


def create_test_brain() -> Brain:

    brain = Brain.__new__(
        Brain
    )

    brain.cognitive = MagicMock()
    brain.memory = MagicMock()

    brain.meta_controller = MagicMock()
    brain.executive_controller = MagicMock()
    brain.director_controller = MagicMock()
    brain.improvement_controller = MagicMock()
    brain.evolution_controller = MagicMock()
    brain.continuous_dev_controller = MagicMock()
    brain.reasoning_service = MagicMock()
    brain.research_service = MagicMock()
    brain.autodev_router = MagicMock()
    brain.planner = MagicMock()
    brain.executor = MagicMock()
    brain.task_planner = MagicMock()
    brain.agent_loop = MagicMock()

    brain.meta_controller.can_handle.return_value = False
    brain.executive_controller.can_handle.return_value = False
    brain.director_controller.can_handle.return_value = False
    brain.improvement_controller.can_handle.return_value = False
    brain.evolution_controller.can_handle.return_value = False
    brain.continuous_dev_controller.can_handle.return_value = False
    brain.reasoning_service.can_handle.return_value = False
    brain.research_service.can_handle.return_value = False
    brain.autodev_router.can_handle.return_value = False

    return brain
