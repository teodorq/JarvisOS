import tempfile
import unittest
from pathlib import Path

from app.autodev.developer_controller import (
    DeveloperController
)
from app.autodev.developer_request import (
    DeveloperRequest
)


class DeveloperControllerTest(unittest.TestCase):

    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.project_root = Path(
            self.temp_directory.name
        )

        self._create_test_project()

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_successful_workflow(self):
        sample_path = (
            self.project_root
            / "app"
            / "sample.py"
        )

        old_content = (
            "VALUE = 1\n\n"
            "\n"
            "def get_value():\n"
            "    return VALUE\n"
        )

        new_content = (
            "VALUE = 2\n\n"
            "\n"
            "def get_value():\n"
            "    return VALUE\n"
        )

        sample_path.write_text(
            old_content,
            encoding="utf-8"
        )

        controller = DeveloperController(
            project_root=str(
                self.project_root
            )
        )

        request = DeveloperRequest(
            goal=(
                "Zmień wartość testową "
                "z 1 na 2."
            ),
            target="app.sample",
            mode="file",
            path=str(sample_path),
            proposed_content=new_content
        )

        prepare_result = controller.prepare(
            request
        )

        self.assertTrue(
            prepare_result.success
        )

        self.assertEqual(
            prepare_result.status,
            "waiting_for_approval"
        )

        self.assertIsNotNone(
            prepare_result.transaction
        )

        self.assertIn(
            "AUTODEV PATCH PREVIEW",
            prepare_result.preview
        )

        self.assertIn(
            "-VALUE = 1",
            prepare_result.preview
        )

        self.assertIn(
            "+VALUE = 2",
            prepare_result.preview
        )

        blocked_result = controller.execute()

        self.assertFalse(
            blocked_result.success
        )

        self.assertEqual(
            blocked_result.status,
            "execution_blocked"
        )

        final_result = (
            controller.approve_and_execute()
        )

        self.assertTrue(
            final_result.success
        )

        self.assertEqual(
            final_result.status,
            "completed"
        )

        self.assertEqual(
            sample_path.read_text(
                encoding="utf-8"
            ),
            new_content
        )

        self.assertIsNotNone(
            final_result.transaction
        )

        self.assertEqual(
            final_result.transaction.status,
            "validated"
        )

        self.assertTrue(
            final_result.transaction
            .backup_bundle_path
        )

        status = controller.status()

        self.assertEqual(
            status["session_status"],
            "completed"
        )

        self.assertFalse(
            status["can_execute"]
        )

        report = controller.report()

        self.assertIn(
            "AUTODEV DEVELOPER CONTROLLER",
            report
        )

        self.assertIn(
            "Status: completed",
            report
        )

    def test_automatic_rollback_after_import_error(
        self
    ):
        main_window_path = (
            self.project_root
            / "app"
            / "gui"
            / "main_window.py"
        )

        old_content = (
            "class MainWindow:\n"
            "    pass\n"
        )

        broken_content = (
            "from module_that_does_not_exist "
            "import MissingClass\n\n"
            "\n"
            "class MainWindow:\n"
            "    pass\n"
        )

        main_window_path.write_text(
            old_content,
            encoding="utf-8"
        )

        controller = DeveloperController(
            project_root=str(
                self.project_root
            )
        )

        request = DeveloperRequest(
            goal=(
                "Przetestuj rollback po "
                "błędzie importu."
            ),
            target="app.gui.main_window",
            mode="file",
            path=str(main_window_path),
            proposed_content=broken_content
        )

        prepare_result = controller.prepare(
            request
        )

        self.assertTrue(
            prepare_result.success
        )

        approval_result = controller.approve()

        self.assertTrue(
            approval_result.success
        )

        execution_result = controller.execute(
            auto_rollback=True
        )

        self.assertFalse(
            execution_result.success
        )

        self.assertEqual(
            execution_result.status,
            "failed_and_rolled_back"
        )

        self.assertEqual(
            main_window_path.read_text(
                encoding="utf-8"
            ),
            old_content
        )

        self.assertIsNotNone(
            execution_result.transaction
        )

        self.assertEqual(
            execution_result.transaction.status,
            "rolled_back"
        )

        self.assertTrue(
            execution_result.data.get(
                "rollback_attempted"
            )
        )

        self.assertTrue(
            execution_result.data.get(
                "rollback_success"
            )
        )

        self.assertEqual(
            controller.session.status,
            "rolled_back"
        )

    def test_reject_patch_without_file_change(
        self
    ):
        sample_path = (
            self.project_root
            / "app"
            / "reject_sample.py"
        )

        old_content = (
            "STATUS = 'OLD'\n"
        )

        new_content = (
            "STATUS = 'NEW'\n"
        )

        sample_path.write_text(
            old_content,
            encoding="utf-8"
        )

        controller = DeveloperController(
            project_root=str(
                self.project_root
            )
        )

        request = DeveloperRequest(
            goal="Przetestuj odrzucenie patcha.",
            target="app.reject_sample",
            mode="file",
            path=str(sample_path),
            proposed_content=new_content
        )

        prepare_result = controller.prepare(
            request
        )

        self.assertTrue(
            prepare_result.success
        )

        reject_result = controller.reject(
            reason="Zmiana nie została zaakceptowana."
        )

        self.assertTrue(
            reject_result.success
        )

        self.assertEqual(
            reject_result.status,
            "rejected"
        )

        self.assertEqual(
            sample_path.read_text(
                encoding="utf-8"
            ),
            old_content
        )

        self.assertEqual(
            controller.session.status,
            "cancelled"
        )

        self.assertFalse(
            controller.session.approved
        )

        self.assertIsNone(
            controller.session.transaction
        )

    def _create_test_project(self):
        app_path = (
            self.project_root
            / "app"
        )

        gui_path = (
            app_path
            / "gui"
        )

        app_path.mkdir(
            parents=True,
            exist_ok=True
        )

        gui_path.mkdir(
            parents=True,
            exist_ok=True
        )

        app_init_path = (
            app_path
            / "__init__.py"
        )

        gui_init_path = (
            gui_path
            / "__init__.py"
        )

        main_window_path = (
            gui_path
            / "main_window.py"
        )

        app_init_path.write_text(
            "",
            encoding="utf-8"
        )

        gui_init_path.write_text(
            "",
            encoding="utf-8"
        )

        main_window_path.write_text(
            (
                "class MainWindow:\n"
                "    pass\n"
            ),
            encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )