import inspect
import unittest

from app.desktop.controller import DesktopController


class TestDesktopController(unittest.TestCase):

    def test_desktop_controller_class_exists(self) -> None:
        self.assertTrue(
            inspect.isclass(
                DesktopController
            )
        )

    def test_required_methods_exist(self) -> None:
        required_methods = (
            "wait",
            "move_mouse",
            "click",
        )

        for method_name in required_methods:
            with self.subTest(
                method=method_name
            ):
                self.assertTrue(
                    hasattr(
                        DesktopController,
                        method_name,
                    )
                )

                self.assertTrue(
                    callable(
                        getattr(
                            DesktopController,
                            method_name,
                        )
                    )
                )

    def test_move_mouse_signature(self) -> None:
        signature = inspect.signature(
            DesktopController.move_mouse
        )

        parameters = list(
            signature.parameters.keys()
        )

        self.assertIn(
            "self",
            parameters,
        )
        self.assertGreaterEqual(
            len(parameters),
            3,
        )

    def test_wait_signature(self) -> None:
        signature = inspect.signature(
            DesktopController.wait
        )

        parameters = list(
            signature.parameters.keys()
        )

        self.assertIn(
            "self",
            parameters,
        )
        self.assertGreaterEqual(
            len(parameters),
            2,
        )


if __name__ == "__main__":
    unittest.main()
