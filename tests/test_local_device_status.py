from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.fast_local_commands import FastLocalCommandService
from app.assistant.local_device_status import format_local_device_status


class _Provider:
    @staticmethod
    def cpu_percent(*, interval=None):
        del interval
        return 17.4

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(percent=53.2)

    @staticmethod
    def disk_usage(_root):
        return SimpleNamespace(free=125.5 * (1024 ** 3))

    @staticmethod
    def boot_time():
        return datetime(2026, 10, 1, 10, 0).timestamp()

    @staticmethod
    def sensors_battery():
        return SimpleNamespace(percent=82.0, power_plugged=True)


class LocalDeviceStatusTests(unittest.TestCase):
    def test_formats_local_resources_power_and_uptime(self) -> None:
        result = format_local_device_status(
            provider=_Provider,
            now=datetime(2026, 10, 2, 12, 35),
        )

        self.assertIn("CPU 17%", result)
        self.assertIn("RAM 53%", result)
        self.assertIn("125.5 GB", result)
        self.assertIn("1 d 2 godz. 35 min", result)
        self.assertIn("zasilanie sieciowe, poziom 82%", result)

    def test_missing_battery_is_reported_naturally(self) -> None:
        class DesktopProvider(_Provider):
            @staticmethod
            def sensors_battery():
                return None

        result = format_local_device_status(
            provider=DesktopProvider,
            now=datetime(2026, 10, 2, 12, 35),
        )

        self.assertIn("bateria niewykryta", result)

    def test_specific_device_question_returns_only_requested_metric(self) -> None:
        cases = (
            ("Pokaż użycie procesora", "użycie procesora: 17%", "RAM"),
            ("Pokaż użycie pamięci RAM", "pamięci RAM: 53%", "CPU"),
            ("Pokaż wolne miejsce na dysku", "125.5 GB", "CPU"),
            ("Pokaż czas pracy komputera", "1 d 2 godz. 35 min", "CPU"),
            ("Pokaż poziom baterii", "poziom 82%", "CPU"),
        )
        for command, expected, excluded in cases:
            with self.subTest(command=command):
                result = format_local_device_status(
                    command,
                    provider=_Provider,
                    now=datetime(2026, 10, 2, 12, 35),
                )
                self.assertIn(expected, result)
                self.assertNotIn(excluded, result)

    def test_provider_failure_returns_safe_message(self) -> None:
        class BrokenProvider:
            @staticmethod
            def cpu_percent(*, interval=None):
                del interval
                raise OSError("probe failed")

        self.assertEqual(
            format_local_device_status(provider=BrokenProvider),
            "Nie udało się teraz odczytać stanu komputera.",
        )

    def test_device_status_is_a_fast_authorized_local_read(self) -> None:
        with TemporaryDirectory() as directory:
            assistant = PersonalAssistantController(Path(directory))
            thought = assistant.plan("Jaki jest stan komputera?")
            result = FastLocalCommandService.try_execute(
                assistant,
                "Jaki jest stan komputera?",
                authorize=lambda *_args, **_kwargs: {"allowed": True},
            )

            self.assertEqual(thought["assistant_intent"], "device_status")
            self.assertTrue(thought["read_only"])
            self.assertIsNotNone(result)
            self.assertEqual(result["handler"], "fast_local_response")
            self.assertIn("komputera", result["message"])

    def test_common_device_questions_are_recognized(self) -> None:
        for command in (
            "Jaki jest stan komputera?",
            "Ile mam baterii?",
            "Jak długo działa komputer?",
            "Pokaż użycie procesora",
        ):
            with self.subTest(command=command):
                self.assertTrue(PersonalAssistantController.matches(command))

    def test_short_device_followups_use_the_previous_topic(self) -> None:
        with TemporaryDirectory() as directory:
            assistant = PersonalAssistantController(Path(directory))
            assistant.handle("Jaki jest stan komputera?")

            for command, resolved in (
                ("A RAM?", "Pokaż użycie pamięci RAM"),
                ("A bateria?", "Pokaż poziom baterii"),
                ("A dysk?", "Pokaż wolne miejsce na dysku"),
                ("A procesor?", "Pokaż użycie procesora"),
                ("A czas pracy?", "Pokaż czas pracy komputera"),
            ):
                with self.subTest(command=command):
                    result = assistant.resolve_command(command)
                    self.assertEqual(result.intent, "device_status")
                    self.assertEqual(result.resolved, resolved)
                    self.assertTrue(result.used_context)


if __name__ == "__main__":
    unittest.main()
