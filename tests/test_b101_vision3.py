from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.intelligence.vision_runtime import VisionRuntimeV3


class B101Vision3Tests(unittest.TestCase):

    def test_observation_uses_stable_element_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            service = VisionRuntimeV3(temporary)
            first = service.observe(
                "Notatnik",
                [{"label": "Zapisz", "role": "button", "bounds": [1, 2, 3, 4]}],
            )
            second = service.observe(
                "Notatnik",
                [{"label": "Zapisz", "role": "button", "bounds": [1, 2, 3, 4]}],
            )
            self.assertEqual(
                first["elements"][0]["element_id"],
                second["elements"][0]["element_id"],
            )
            self.assertEqual(second["changes"]["added"], [])

    def test_select_returns_best_visible_element(self) -> None:
        with TemporaryDirectory() as temporary:
            service = VisionRuntimeV3(temporary)
            service.observe(
                "JARVIS",
                [
                    {"label": "Anuluj", "role": "button", "confidence": 0.9},
                    {"label": "Wykonaj polecenie", "role": "button", "confidence": 0.98},
                ],
            )
            selected = service.select("wykonaj")
            self.assertEqual(selected["label"], "Wykonaj polecenie")

    def test_action_verification_checks_expected_state(self) -> None:
        with TemporaryDirectory() as temporary:
            service = VisionRuntimeV3(temporary)
            observation = service.observe(
                "Kalkulator",
                [{"label": "Wynik 4", "role": "text"}],
            )
            service.begin_verification(
                "action-1",
                {"window_contains": "kalk", "text_contains": "wynik 4"},
            )
            result = service.verify("action-1", observation)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertTrue(all(result["checks"].values()))

    def test_history_is_bounded(self) -> None:
        with TemporaryDirectory() as temporary:
            service = VisionRuntimeV3(temporary)
            for index in range(90):
                service.observe(f"Okno {index}")
            self.assertEqual(service.status()["observation_count"], 80)


if __name__ == "__main__":
    unittest.main()
