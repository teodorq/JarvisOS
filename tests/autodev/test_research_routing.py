import unittest

from app.ai.autodev_router import (
    AutoDevRouter
)
from app.ai.brain import Brain
from app.autodev.research_router import (
    ResearchRouter
)


class ResearchRouterTest(
    unittest.TestCase
):

    def setUp(
        self
    ):
        self.research_router = (
            ResearchRouter(
                project_root="C:/JarvisAI"
            )
        )

        self.autodev_router = (
            AutoDevRouter(
                project_root="C:/JarvisAI"
            )
        )

    def test_research_commands_are_detected(
        self
    ):
        commands = [
            (
                "Przeanalizuj moduł Vision"
            ),
            (
                "Sprawdź jakość kodu Brain"
            ),
            (
                "Zaplanuj refaktoryzację Memory"
            ),
            (
                "Znajdź problemy w kodzie JARVIS"
            ),
            (
                "Oceń architekturę AutoDev"
            )
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    self.research_router
                    .can_handle(
                        command
                    )
                )

    def test_standard_commands_are_not_research(
        self
    ):
        commands = [
            "Sprawdź pogodę",
            "Sprawdź godzinę",
            "Otwórz YouTube",
            "Wyszukaj muzykę",
            "Pokaż kalendarz",
            "Otwórz Gmail"
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertFalse(
                    self.research_router
                    .can_handle(
                        command
                    )
                )

    def test_autodev_commands_are_not_research(
        self
    ):
        commands = [
            "Pokaż status AutoDev",
            "Pokaż raport AutoDev",
            "Pokaż patch",
            "Zaakceptuj patch",
            "Wykonaj patch",
            "Odrzuć patch",
            "Rollback AutoDev",
            "Zresetuj AutoDev"
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertFalse(
                    self.research_router
                    .can_handle(
                        command
                    )
                )

    def test_autodev_router_detects_control_commands(
        self
    ):
        commands = [
            "Pokaż status AutoDev",
            "Pokaż raport AutoDev",
            "Pokaż patch",
            "Zaakceptuj patch",
            "Wykonaj patch",
            "Odrzuć patch",
            "Rollback AutoDev",
            "Zresetuj AutoDev"
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    self.autodev_router
                    .can_handle(
                        command
                    )
                )


class BrainRoutingTest(
    unittest.TestCase
):

    def setUp(
        self
    ):
        self.brain = Brain()

    def test_brain_routes_research_command(
        self
    ):
        thought = self.brain.think(
            "Przeanalizuj moduł Vision"
        )

        self.assertEqual(
            thought.get(
                "handler"
            ),
            "research"
        )

        self.assertTrue(
            thought.get(
                "can_execute"
            )
        )

        self.assertEqual(
            thought.get(
                "actions"
            ),
            []
        )

    def test_brain_routes_autodev_command(
        self
    ):
        thought = self.brain.think(
            "Pokaż status AutoDev"
        )

        self.assertEqual(
            thought.get(
                "handler"
            ),
            "autodev"
        )

        self.assertTrue(
            thought.get(
                "can_execute"
            )
        )

    def test_brain_routes_standard_command(
        self
    ):
        thought = self.brain.think(
            "Otwórz YouTube"
        )

        self.assertEqual(
            thought.get(
                "handler"
            ),
            "standard"
        )

        self.assertNotEqual(
            thought.get(
                "handler"
            ),
            "research"
        )

        self.assertNotEqual(
            thought.get(
                "handler"
            ),
            "autodev"
        )

    def test_weather_does_not_start_research(
        self
    ):
        thought = self.brain.think(
            "Sprawdź pogodę"
        )

        self.assertEqual(
            thought.get(
                "handler"
            ),
            "standard"
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )