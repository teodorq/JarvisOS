import inspect
import unittest

from app.automation.command_executor import CommandExecutor


class TestCommandExecutor(unittest.TestCase):

    def test_command_executor_class_exists(self) -> None:
        self.assertTrue(
            inspect.isclass(CommandExecutor)
        )

    def test_execute_action_method_exists(self) -> None:
        self.assertTrue(
            hasattr(
                CommandExecutor,
                "execute_action",
            )
        )

        self.assertTrue(
            callable(
                getattr(
                    CommandExecutor,
                    "execute_action",
                )
            )
        )

    def test_execute_action_accepts_action_argument(self) -> None:
        signature = inspect.signature(
            CommandExecutor.execute_action
        )

        parameters = list(
            signature.parameters.keys()
        )

        self.assertIn(
            "self",
            parameters,
        )
        self.assertIn(
            "action",
            parameters,
        )


if __name__ == "__main__":
    unittest.main()
