from __future__ import annotations

import json
from pathlib import Path
import unittest

from app.gui.client_command_runtime import ClientCommandRuntimeMixin
from app.gui.client_result_formatter import ClientResultFormatter
from app.jarvis_experience.isolation import (
    ClientIsolationPolicy,
    TrustedActionResult,
)
from app.jarvis_experience.smart_task_loop import SmartTaskLoop, TaskOutcome


class _ClientRuntime(ClientCommandRuntimeMixin):
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.spoken: list[str] = []

    def _publish_client_event(self, **event) -> None:
        self.events.append(ClientIsolationPolicy.sanitize_event(event))

    def say_safe(self, text: str) -> None:
        self.spoken.append(text)


class TestB331B340ReadableClientResults(unittest.TestCase):
    def test_manifest_closes_all_ten_stages(self) -> None:
        manifest = json.loads(
            Path("config/b331_b340_readable_client_results.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(331, 341)],
        )
        self.assertTrue(
            all(value.endswith("READY") for value in manifest["stages"].values())
        )
        self.assertTrue(manifest["safety"]["owner_data_hidden"])
        self.assertTrue(manifest["safety"]["owner_gate_unchanged"])

    def test_mail_wall_of_text_becomes_a_readable_card(self) -> None:
        message = (
            "B126 Najnowsze wiadomości Gmail: 5 "
            "1. Biuro <biuro@example.com> — Potwierdzenie spotkania "
            "2. Sklep <sklep@example.com> — Faktura "
            "3. Bank <bank@example.com> — Nowe logowanie "
            "4. Zespół <team@example.com> — Raport "
            "5. Ala <ala@example.com> — Pytanie"
        )
        card = ClientResultFormatter.format(message, result_type="mail")
        self.assertEqual(card.title, "POCZTA")
        self.assertEqual(card.summary, "Znalazłem 5 wiadomości.")
        self.assertIn("\n2. Sklep", card.body)
        self.assertNotIn("B126", card.body)
        self.assertEqual(card.body.count("\n"), 4)
        self.assertEqual(
            card.spoken,
            "Znalazłem 5 wiadomości. Szczegóły wyświetliłem na ekranie.",
        )

    def test_polish_counts_are_natural_for_each_result_type(self) -> None:
        cases = (
            ("calendar", 5, "Masz 5 wydarzeń."),
            ("documents", 2, "Znalazłem 2 dokumenty."),
            ("reminders", 1, "Masz jedno przypomnienie."),
        )
        for kind, count, expected in cases:
            details = "\n".join(f"{index}. Element" for index in range(1, count + 1))
            with self.subTest(kind=kind, count=count):
                card = ClientResultFormatter.format(details, result_type=kind)
                self.assertEqual(card.summary, expected)

    def test_error_always_uses_attention_card(self) -> None:
        card = ClientResultFormatter.format(
            "Nie udało się odczytać poczty.",
            state="error",
            result_type="mail",
        )
        self.assertEqual(card.kind, "error")
        self.assertEqual(card.title, "WYMAGANA UWAGA")

    def test_result_category_is_strictly_allowlisted(self) -> None:
        clean = ClientIsolationPolicy.sanitize_event(
            {
                "state": "success",
                "message": "Gotowe",
                "result_type": "mail",
                "owner_secret": "hidden",
            }
        )
        self.assertEqual(clean["result_type"], "mail")
        self.assertNotIn("owner_secret", clean)
        blocked = ClientIsolationPolicy.sanitize_event(
            {"state": "success", "result_type": "owner_console"}
        )
        self.assertEqual(blocked["result_type"], "")

    def test_safe_read_results_keep_line_breaks(self) -> None:
        loop = SmartTaskLoop(None, lambda *_args: {"allowed": True}, lambda _: True)
        outcome = loop.execute(
            {"assistant_intent": "gmail_latest", "read_only": True},
            executor=lambda _thought: "B126 Poczta:\n1. Pierwsza\n2. Druga",
        )
        self.assertIsInstance(outcome.message, TrustedActionResult)
        self.assertIn("\n2. Druga", outcome.message)

    def test_runtime_speaks_summary_and_publishes_details(self) -> None:
        runtime = _ClientRuntime()
        runtime._finish_client_outcome(
            TaskOutcome(
                "COMPLETED",
                TrustedActionResult("Poczta:\n1. Pierwsza\n2. Druga"),
                thought={"assistant_intent": "gmail_search"},
            )
        )
        self.assertEqual(runtime.events[0]["result_type"], "mail")
        self.assertIn("\n2. Druga", runtime.events[0]["message"])
        self.assertEqual(
            runtime.spoken,
            ["Znalazłem 2 wiadomości. Szczegóły wyświetliłem na ekranie."],
        )

    def test_gui_integration_uses_structured_result_cards(self) -> None:
        root = Path(__file__).resolve().parents[1]
        experience = (root / "app/gui/client_experience_v2.py").read_text(
            encoding="utf-8"
        )
        theme = (root / "app/gui/client_theme.py").read_text(encoding="utf-8")
        self.assertIn("ClientResultFormatter", experience)
        self.assertIn("ConversationResultCard", experience)
        self.assertIn("ConversationResultCard", theme)
        self.assertLess(len(theme.splitlines()), 120)


if __name__ == "__main__":
    unittest.main()
