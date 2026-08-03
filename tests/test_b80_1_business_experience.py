from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import warnings

from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)
from app.business.business_config import BusinessConfigStore
from app.business.business_edition_service import BusinessEditionService
from app.gui.command_safety import is_read_only_learning_command


class B801BusinessConfigurationTests(unittest.TestCase):
    def test_schema_two_ui_defaults_are_hardened(self) -> None:
        with TemporaryDirectory() as directory:
            config = BusinessConfigStore(directory).ensure()
            self.assertEqual(config["schema_version"], 2)
            self.assertEqual(config["ui"]["start_page"], "console")
            self.assertTrue(config["ui"]["show_quick_actions"])
            self.assertEqual(config["ui"]["density"], "comfortable")
            self.assertFalse(config["safety"]["auto_approve"])
            self.assertEqual(config["safety"]["max_active_executions"], 1)

    def test_invalid_ui_values_are_safely_normalized(self) -> None:
        with TemporaryDirectory() as directory:
            store = BusinessConfigStore(directory)
            config = store.update({
                "ui": {
                    "start_page": "shell",
                    "show_quick_actions": 0,
                    "density": "unsafe-dense",
                },
                "safety": {
                    "auto_approve": True,
                    "max_active_executions": 20,
                },
            })
            self.assertEqual(config["ui"]["start_page"], "console")
            self.assertFalse(config["ui"]["show_quick_actions"])
            self.assertEqual(config["ui"]["density"], "comfortable")
            self.assertFalse(config["safety"]["auto_approve"])
            self.assertEqual(config["safety"]["max_active_executions"], 1)

    def test_reset_restores_safe_business_defaults(self) -> None:
        with TemporaryDirectory() as directory:
            store = BusinessConfigStore(directory)
            store.update({
                "organization": "Example Company",
                "accent_color": "#55D98B",
                "ui": {"show_quick_actions": False},
            })
            reset = store.reset()
            self.assertEqual(reset["organization"], "Kacper")
            self.assertEqual(reset["accent_color"], "#4DA3FF")
            self.assertTrue(reset["ui"]["show_quick_actions"])


class B801BusinessServiceTests(unittest.TestCase):
    def test_status_exposes_b801_release_and_ui(self) -> None:
        with TemporaryDirectory() as directory:
            status = BusinessEditionService(directory).status()
            self.assertEqual(status["stage"], "B80")
            self.assertEqual(status["business"]["release"], "B80.1")
            self.assertEqual(status["business"]["ui"]["start_page"], "console")
            self.assertTrue(status["license"]["active"])

    def test_license_and_integrity_views_are_read_only_snapshots(self) -> None:
        with TemporaryDirectory() as directory:
            service = BusinessEditionService(directory)
            license_status = service.license_details()
            integrity_status = service.integrity_status()
            self.assertEqual(license_status["status"], "BUSINESS_EDITION_LICENSE")
            self.assertEqual(license_status["decision"], "ACTIVE")
            self.assertEqual(
                integrity_status["status"],
                "BUSINESS_EDITION_INTEGRITY",
            )
            self.assertEqual(integrity_status["decision"], "BASELINE_PENDING")


class B801BusinessRoutingTests(unittest.TestCase):
    def test_router_recognizes_license_and_integrity_commands(self) -> None:
        router = SoftwareEngineerAutonomyOperationsRouter()
        commands = (
            "Pokaż licencję Business Edition",
            "Pokaż integralność Business Edition",
            "Business Edition license",
            "Business Edition integrity",
        )
        for command in commands:
            self.assertTrue(router.can_handle(command), command)
            self.assertTrue(is_read_only_learning_command(command), command)

    def test_router_dispatches_license_and_integrity_views(self) -> None:
        service = SimpleNamespace(
            license_details=lambda: {"status": "LICENSE"},
            integrity_status=lambda: {"status": "INTEGRITY"},
        )
        suite = SimpleNamespace(business_edition=service)
        router = SoftwareEngineerAutonomyOperationsRouter()
        license_result = router.try_handle(
            suite,
            command="pokaż licencję business edition",
        )
        integrity_result = router.try_handle(
            suite,
            command="pokaż integralność business edition",
        )
        self.assertEqual(license_result["status"], "LICENSE")
        self.assertEqual(integrity_result["status"], "INTEGRITY")


class B801BusinessUiStructureTests(unittest.TestCase):
    def test_business_experience_has_navigation_and_three_pages(self) -> None:
        root = Path(__file__).resolve().parents[1]
        window = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        pages = (root / "app/gui/business_pages.py").read_text(encoding="utf-8")
        widgets = (root / "app/gui/business_widgets.py").read_text(encoding="utf-8")
        theme = (root / "app/gui/business_theme.py").read_text(encoding="utf-8")
        self.assertIn("COMMAND CONSOLE", window)
        self.assertIn("ORGANIZATION", window)
        self.assertIn("LICENSE & TRUST", window)
        self.assertIn("class ConsolePage", pages)
        self.assertIn("class SettingsPage", pages)
        self.assertIn("class TrustPage", pages)
        self.assertIn("QuickCommandButton", pages)
        self.assertIn("class NavigationButton", widgets)
        self.assertIn('tone="healthy"', theme)

    def test_business_ui_files_stay_below_audit_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/main_window.py": 440,
            "app/gui/business_pages.py": 440,
            "app/gui/business_widgets.py": 220,
            "app/gui/business_command_runtime.py": 180,
            "app/gui/business_theme.py": 260,
            "app/business/business_config.py": 180,
            "app/business/business_edition_service.py": 190,
            "app/ai/software_engineer/software_engineer_autonomy_operations_router.py": 440,
        }
        for relative, limit in limits.items():
            count = len((root / relative).read_text(encoding="utf-8").splitlines())
            self.assertLess(count, limit, f"{relative}: {count} not below {limit}")

    def test_demo_services_compile_without_syntax_warnings(self) -> None:
        root = Path(__file__).resolve().parents[1]
        paths = (
            root / "app/long_running_demo/service.py",
            root / "app/long_running_demo_b54_test/service.py",
        )
        for path in paths:
            source = path.read_text(encoding="utf-8")
            with warnings.catch_warnings():
                warnings.simplefilter("error", SyntaxWarning)
                compile(source, str(path), "exec")


if __name__ == "__main__":
    unittest.main()
