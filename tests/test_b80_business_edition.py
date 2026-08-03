from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_autonomy_operations_formatter import (
    format_autonomy_operations_response,
)
from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)
from app.business.business_config import BusinessConfigStore
from app.business.business_edition_service import BusinessEditionService
from app.business.business_license import BusinessLicenseManager
from app.gui.command_safety import is_read_only_learning_command


class B80BusinessConfigTests(unittest.TestCase):
    def test_defaults_are_business_and_safety_hardened(self) -> None:
        with TemporaryDirectory() as directory:
            config = BusinessConfigStore(directory).ensure()
            self.assertEqual(config["edition"], "BUSINESS")
            self.assertEqual(config["product_name"], "JARVIS OS")
            self.assertFalse(config["safety"]["auto_approve"])
            self.assertTrue(config["safety"]["require_confirmation"])
            self.assertEqual(config["safety"]["max_active_executions"], 1)
            self.assertFalse(config["safety"]["allow_remote_code_execution"])

    def test_update_cannot_enable_unsafe_business_flags(self) -> None:
        with TemporaryDirectory() as directory:
            store = BusinessConfigStore(directory)
            config = store.update({
                "edition": "PERSONAL",
                "accent_color": "not-a-color",
                "safety": {
                    "auto_approve": True,
                    "require_confirmation": False,
                    "max_active_executions": 99,
                    "allow_remote_code_execution": True,
                },
            })
            self.assertEqual(config["edition"], "BUSINESS")
            self.assertEqual(config["accent_color"], "#4DA3FF")
            self.assertFalse(config["safety"]["auto_approve"])
            self.assertTrue(config["safety"]["require_confirmation"])
            self.assertEqual(config["safety"]["max_active_executions"], 1)
            self.assertFalse(config["safety"]["allow_remote_code_execution"])


class B80LicenseTests(unittest.TestCase):
    def test_owner_development_license_is_active_locally(self) -> None:
        with TemporaryDirectory() as directory:
            config = BusinessConfigStore(directory).ensure()
            status = BusinessLicenseManager(directory).status(config)
            self.assertTrue(status["active"])
            self.assertEqual(status["status"], "OWNER_DEVELOPMENT")
            self.assertFalse(status["commercial_activation"])
            self.assertEqual(len(status["machine_fingerprint"]), 16)

    def test_commercial_license_integrity_and_expiry_are_validated(self) -> None:
        with TemporaryDirectory() as directory:
            config = BusinessConfigStore(directory).ensure()
            manager = BusinessLicenseManager(directory)
            manager.save_license({
                "product_code": "JARVIS-OS-BUSINESS",
                "mode": "COMMERCIAL",
                "license_id": "BUSINESS-001",
                "organization": "Example Company",
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(days=30)
                ).isoformat(),
            })
            status = manager.status(config)
            self.assertTrue(status["active"])
            self.assertEqual(status["status"], "ACTIVE")
            self.assertTrue(status["commercial_activation"])

            payload = manager._store.load()
            payload["organization"] = "Tampered"
            manager._store.save(payload)
            invalid = manager.status(config)
            self.assertFalse(invalid["active"])
            self.assertEqual(invalid["status"], "INTEGRITY_FAILED")


class B80IntegrityAndServiceTests(unittest.TestCase):
    def test_integrity_baseline_is_pending_before_installer_manifest(self) -> None:
        with TemporaryDirectory() as directory:
            service = BusinessEditionService(directory)
            result = service.verify_integrity()
            self.assertEqual(result["status"], "BASELINE_PENDING")

    def test_integrity_manifest_detects_source_change(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app" / "sample.py"
            target.parent.mkdir(parents=True)
            target.write_text("VALUE = 1\n", encoding="utf-8")
            service = BusinessEditionService(root)
            service.create_integrity_manifest(["app/sample.py"])
            self.assertEqual(service.verify_integrity()["status"], "VERIFIED")
            target.write_text("VALUE = 2\n", encoding="utf-8")
            changed = service.verify_integrity()
            self.assertEqual(changed["status"], "CHANGED")
            self.assertEqual(changed["changed"], ["app/sample.py"])

    def test_status_exposes_business_license_integrity_and_safety(self) -> None:
        with TemporaryDirectory() as directory:
            result = BusinessEditionService(directory).status()
            self.assertTrue(result["success"])
            self.assertEqual(result["stage"], "B80")
            self.assertEqual(result["status"], "BUSINESS_EDITION_STATUS")
            self.assertEqual(result["runtime"]["phase"], "READY")
            self.assertEqual(result["business"]["edition"], "BUSINESS")
            self.assertEqual(result["license"]["status"], "OWNER_DEVELOPMENT")
            self.assertFalse(result["safety"]["auto_approve"])
            self.assertEqual(result["safety"]["max_active_executions"], 1)


class B80RoutingAndFormattingTests(unittest.TestCase):
    def test_router_recognizes_polish_and_english_business_status(self) -> None:
        router = SoftwareEngineerAutonomyOperationsRouter()
        self.assertTrue(router.can_handle("Pokaż status Business Edition"))
        self.assertTrue(router.can_handle("Business Edition status"))
        self.assertTrue(router.can_handle("Pokaż konfigurację Business Edition"))

    def test_router_dispatches_status_and_configuration(self) -> None:
        service = SimpleNamespace(
            status=lambda: {"stage": "B80", "status": "STATUS"},
            configuration=lambda: {"stage": "B80", "status": "CONFIG"},
        )
        suite = SimpleNamespace(business_edition=service)
        router = SoftwareEngineerAutonomyOperationsRouter()
        status = router.try_handle(
            suite,
            command="pokaż status business edition",
        )
        config = router.try_handle(
            suite,
            command="pokaż konfigurację business edition",
        )
        self.assertEqual(status["status"], "STATUS")
        self.assertEqual(config["status"], "CONFIG")

    def test_b80_status_is_safe_read_only_command(self) -> None:
        self.assertTrue(is_read_only_learning_command("Pokaż status Business Edition"))
        self.assertTrue(
            is_read_only_learning_command("Pokaż konfigurację Business Edition")
        )

    def test_controller_can_route_business_status(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Pokaż status Business Edition"
            )
        )

    def test_formatter_reports_business_state(self) -> None:
        text = format_autonomy_operations_response({
            "stage": "B80",
            "status": "BUSINESS_EDITION_STATUS",
            "runtime": {"phase": "READY", "cycles_completed": 0},
            "business": {
                "product_name": "JARVIS OS",
                "organization": "Kacper",
                "environment": "OWNER DEVELOPMENT",
            },
            "license": {
                "status": "OWNER_DEVELOPMENT",
                "mode": "OWNER_DEVELOPMENT",
            },
            "integrity": {"status": "VERIFIED", "files_checked": 12},
            "safety": {"auto_approve": False, "max_active_executions": 1},
            "errors": [],
        })
        self.assertIn("Autonomia JARVIS B80", text)
        self.assertIn("JARVIS OS", text)
        self.assertIn("OWNER_DEVELOPMENT", text)
        self.assertIn("Integralność: VERIFIED", text)
        self.assertIn("auto-approve NIE", text)


class B80UiStructureTests(unittest.TestCase):
    def test_business_ui_is_split_into_theme_widgets_and_window(self) -> None:
        root = Path(__file__).resolve().parents[1]
        window = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        theme = (root / "app/gui/business_theme.py").read_text(encoding="utf-8")
        widgets = (root / "app/gui/business_widgets.py").read_text(encoding="utf-8")
        self.assertIn("BUSINESS COMMAND CENTER", window)
        self.assertIn("BusinessTheme.stylesheet", window)
        self.assertIn("MetricCard", window)
        self.assertIn("OWNER DEVELOPMENT LICENSE", window)
        self.assertIn("QFrame#Header", theme)
        self.assertIn("class MetricCard", widgets)

    def test_business_files_stay_below_audit_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/main_window.py": 440,
            "app/business/business_config.py": 180,
            "app/business/business_license.py": 180,
            "app/business/business_edition_service.py": 190,
            "app/ai/software_engineer/software_engineer_autonomy_operations_router.py": 440,
        }
        for relative, limit in limits.items():
            count = len((root / relative).read_text(encoding="utf-8").splitlines())
            self.assertLess(count, limit, f"{relative}: {count} not below {limit}")


if __name__ == "__main__":
    unittest.main()
