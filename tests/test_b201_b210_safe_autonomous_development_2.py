from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.safe_autonomous_development_service import (
    SafeAutonomousDevelopmentService,
)
from app.ai.software_engineer.safe_development_commands import (
    execute_safe_development_command,
    plan_safe_development_command,
)
from app.ai.software_engineer.safe_development_models import SafeDevelopmentPolicy
from app.ai.software_engineer.safe_development_store import SafeDevelopmentStore
from app.ai.software_engineer.safe_development_transform import SafeTransformPlanner
from app.ai.software_engineer.safe_development_validation import SafeDevelopmentValidator
from app.gui.command_safety import is_safe_workspace_preparation_thought


class B201B210SafeAutonomousDevelopment2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "tools").mkdir()
        (self.root / "config").mkdir()
        (self.root / "app" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        self.target = self.root / "app" / "sample.py"
        self.original = (
            "from __future__ import annotations\n\n"
            "VALUE = 1\n\n"
            "def add(left: int, right: int) -> int:\n"
            "    return left + right\n"
        )
        self.target.write_text(self.original, encoding="utf-8")
        (self.root / "tests" / "test_sample.py").write_text(
            "import unittest\n"
            "from app.sample import add\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )
        source_root = Path(__file__).resolve().parents[1]
        for name in (
            "safe_development_unittest_runner.py",
            "safe_development_import_runner.py",
        ):
            shutil.copy2(source_root / "tools" / name, self.root / "tools" / name)
        config = json.loads(
            (source_root / "config" / "b201_b210_safe_autonomous_development_2.json")
            .read_text(encoding="utf-8")
        )
        (self.root / "config" / "b201_b210_safe_autonomous_development_2.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        self.preview = {
            "task": {
                "target": "app/sample.py",
                "title": "Usprawnij moduł sample",
                "description": "Moduł wymaga bezpiecznego pierwszego kroku.",
            },
            "predicted_risk": 15,
            "effort_score": 10,
        }
        self.policy = SafeDevelopmentPolicy(
            focused_test_limit=4,
            focused_test_timeout_seconds=60,
            live_test_timeout_seconds=60,
        )
        self.service = SafeAutonomousDevelopmentService(
            self.root,
            policy=self.policy,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _prepare(self) -> dict:
        result = self.service.prepare(preview=self.preview)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "READY_FOR_APPROVAL")
        return result

    def test_b201_preview_is_persisted_for_the_next_safe_stage(self) -> None:
        store = SafeDevelopmentStore(self.root, policy=self.policy)
        store.record_preview(self.preview)
        self.assertEqual(store.last_preview()["task"]["target"], "app/sample.py")

    def test_b202_preferred_target_gets_deterministic_transform(self) -> None:
        candidate = SafeTransformPlanner(
            self.root, policy=self.policy
        ).select(self.preview)
        self.assertEqual(candidate.target, "app/sample.py")
        self.assertEqual(candidate.transform, "ADD_MODULE_DOCSTRING")
        changed = SafeTransformPlanner(self.root, policy=self.policy).apply(
            candidate, self.original
        )
        self.assertIsNotNone(ast.get_docstring(ast.parse(changed)))

    def test_b203_prepare_changes_only_isolated_workspace(self) -> None:
        result = self._prepare()
        session = result["session"]
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)
        workspace_target = Path(session["workspace_path"]) / "app" / "sample.py"
        self.assertNotEqual(workspace_target.read_text(encoding="utf-8"), self.original)
        self.assertEqual(session["changed_files"], ["app/sample.py"])

    def test_b204_patch_manifest_and_artifact_hashes_are_exact(self) -> None:
        session = self._prepare()["session"]
        manifest_path = Path(session["metadata"]["manifest_artifact"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        proposed = Path(session["proposed_artifact"]).read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(proposed.encode()).hexdigest(),
            manifest["proposed_hash"],
        )
        self.assertGreater(manifest["changed_lines"], 0)
        self.assertTrue(Path(session["diff_artifact"]).read_text(encoding="utf-8"))

    def test_b205_static_guard_keeps_public_api_unchanged(self) -> None:
        prepared = self._prepare()["session"]
        validation = prepared["validation"]["static"]
        self.assertTrue(validation["checks"]["public_api_unchanged"])
        self.assertTrue(validation["checks"]["transform_exact"])

    def test_b205_dangerous_introduction_is_rejected(self) -> None:
        session = self.service.store.new_session(
            target="app/sample.py",
            transform="ENSURE_FINAL_NEWLINE",
            title="unsafe",
            rationale="unsafe",
            risk_score=1,
            confidence=1,
        )
        session.changed_files = ["app/sample.py"]
        session.changed_lines = 1
        proposed = self.original + "\nos.system('bad')\n"
        session.source_hash = hashlib.sha256(self.original.encode()).hexdigest()
        session.proposed_hash = hashlib.sha256(proposed.encode()).hexdigest()
        result = SafeDevelopmentValidator(
            self.root, policy=self.policy
        ).static_validate(session, original=self.original, proposed=proposed)
        self.assertFalse(result["success"])
        self.assertIn("os.system(", result["checks"]["forbidden_introductions"])

    def test_b206_isolated_compile_import_and_tests_pass(self) -> None:
        session = self._prepare()["session"]
        workspace = session["validation"]["workspace"]
        self.assertTrue(workspace["compile"]["success"])
        self.assertTrue(workspace["import"]["success"])
        self.assertTrue(workspace["tests"]["success"])
        self.assertGreaterEqual(workspace["tests"]["count"], 1)

    def test_b206_validation_runtime_cache_is_removed(self) -> None:
        session = self._prepare()["session"]
        workspace = Path(session["workspace_path"])
        cleanup = session["validation"]["runtime_cleanup"]
        self.assertTrue(cleanup["success"], cleanup)
        self.assertGreater(
            cleanup["removed_files"] + cleanup["removed_directories"],
            0,
        )
        self.assertFalse(list(workspace.rglob("*.pyc")))
        self.assertFalse([
            path for path in workspace.rglob("*")
            if path.is_dir()
            and path.name in {"__pycache__", ".pytest_cache", ".safe_development"}
        ])

    def test_b206_expired_campaign_deadline_stops_before_preparation(self) -> None:
        result = self.service.prepare(
            preview=self.preview,
            deadline_monotonic=time.monotonic() - 1.0,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RUNTIME_BUDGET_REACHED")
        self.assertFalse(result["project_files_modified"])
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b207_prepare_route_is_safe_without_confirmation(self) -> None:
        brain = MagicMock()
        brain.project_root = self.root
        thought = plan_safe_development_command(
            brain,
            "Przygotuj bezpieczną poprawkę na kopii, ale jej nie wdrażaj",
        )
        self.assertEqual(thought["handler"], "safe_development_prepare")
        self.assertFalse(thought["requires_confirmation"])
        self.assertTrue(is_safe_workspace_preparation_thought(thought))

    def test_b207_deploy_plan_is_bound_to_exact_session_and_hash(self) -> None:
        prepared = self._prepare()["session"]
        planned = self.service.plan_deploy()
        self.assertEqual(planned["session"]["session_id"], prepared["session_id"])
        self.assertEqual(
            planned["operation_fingerprint"], prepared["fingerprint"]
        )
        self.assertIn("Czy wdrożyć dokładnie", planned["confirmation_message"])

    def test_b208_confirmed_deployment_modifies_exactly_one_live_file(self) -> None:
        prepared = self._prepare()["session"]
        result = self.service.deploy(
            prepared["session_id"], prepared["fingerprint"]
        )
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "DEPLOYED")
        self.assertNotEqual(self.target.read_text(encoding="utf-8"), self.original)
        self.assertEqual(result["session"]["changed_files"], ["app/sample.py"])

    def test_b208_duplicate_deployment_is_blocked(self) -> None:
        prepared = self._prepare()["session"]
        first = self.service.deploy(prepared["session_id"], prepared["fingerprint"])
        second = self.service.deploy(prepared["session_id"], prepared["fingerprint"])
        self.assertTrue(first["success"])
        self.assertEqual(second["status"], "ALREADY_DEPLOYED")

    def test_b208_wrong_fingerprint_never_writes_project(self) -> None:
        prepared = self._prepare()["session"]
        result = self.service.deploy(prepared["session_id"], "wrong")
        self.assertEqual(result["status"], "CONFIRMATION_MISMATCH")
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b209_stale_source_guard_blocks_deployment(self) -> None:
        prepared = self._prepare()["session"]
        self.target.write_text(self.original + "\nCHANGED = True\n", encoding="utf-8")
        result = self.service.deploy(
            prepared["session_id"], prepared["fingerprint"]
        )
        self.assertEqual(result["status"], "SOURCE_CHANGED")
        self.assertIn("CHANGED = True", self.target.read_text(encoding="utf-8"))

    def test_b209_manual_rollback_restores_verified_original(self) -> None:
        prepared = self._prepare()["session"]
        deployed = self.service.deploy(
            prepared["session_id"], prepared["fingerprint"]
        )
        self.assertTrue(deployed["success"])
        planned = self.service.plan_rollback()
        rolled = self.service.rollback(
            prepared["session_id"], planned["operation_fingerprint"]
        )
        self.assertTrue(rolled["success"], rolled)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b209_rollback_does_not_overwrite_newer_live_change(self) -> None:
        prepared = self._prepare()["session"]
        self.service.deploy(prepared["session_id"], prepared["fingerprint"])
        self.target.write_text(
            self.target.read_text(encoding="utf-8") + "\nNEWER = 1\n",
            encoding="utf-8",
        )
        planned = self.service.plan_rollback()
        result = self.service.rollback(
            prepared["session_id"], planned["operation_fingerprint"]
        )
        self.assertEqual(result["status"], "ROLLBACK_SOURCE_CHANGED")
        self.assertIn("NEWER = 1", self.target.read_text(encoding="utf-8"))

    def test_b210_status_and_discard_are_natural_and_non_mutating(self) -> None:
        self._prepare()
        status = self.service.status()
        self.assertIn("czeka na decyzję", status["message"])
        discarded = self.service.discard()
        self.assertEqual(discarded["status"], "DISCARDED")
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b210_policy_never_auto_approves_or_auto_deploys(self) -> None:
        policy = self.service.policy
        self.assertFalse(policy.auto_approve)
        self.assertFalse(policy.auto_deploy)
        self.assertTrue(policy.auto_rollback)

    def test_b210_command_execution_uses_same_prepared_session(self) -> None:
        brain = MagicMock()
        brain.project_root = self.root
        brain.last_safe_autodev_preview = self.preview
        brain.safe_autonomous_development_service = self.service
        prepare = plan_safe_development_command(
            brain, "Przygotuj bezpieczną poprawkę na kopii"
        )
        message = execute_safe_development_command(brain, prepare)
        self.assertIn("izolowanej kopii", message)
        deploy = plan_safe_development_command(
            brain, "Wdróż przygotowaną poprawkę"
        )
        self.assertEqual(deploy["handler"], "safe_development_deploy")
        self.assertTrue(deploy["operation_fingerprint"])
        self.assertTrue(deploy["safe_session_id"].startswith("safe-dev-"))

    def test_b210_router_priority_source_bounds_and_config(self) -> None:
        root = Path(__file__).resolve().parents[1]
        router = (root / "app" / "ai" / "brain_command_router.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(router.splitlines()), 200)

        self.assertLess(
            router.index("plan_safe_development_command"),
            router.index("software_engineer_controller ="),
        )
        self.assertIn("handler.startswith('safe_development_')", router)
        commands = (
            root / "app" / "ai" / "software_engineer" / "safe_development_commands.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(commands.splitlines()), 360)
        config = json.loads(
            (root / "config" / "b201_b210_safe_autonomous_development_2.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertFalse(config["safety"]["auto_deploy"])
        self.assertEqual(config["limits"]["max_changed_files"], 1)

    def test_structural_goal_rejects_cosmetic_docstring(self) -> None:
        session = self.service.store.new_session(
            target="app/sample.py",
            transform="ADD_FUNCTION_DOCSTRING",
            title="cosmetic",
            rationale="cosmetic",
            risk_score=1,
            confidence=1,
            metadata={"function": "add", "issue_type": "LONG_FUNCTION"},
        )
        proposed = SafeTransformPlanner._add_function_docstring(
            self.original,
            "app/sample.py",
            "add",
        )
        session.changed_files = ["app/sample.py"]
        session.changed_lines = 1
        session.source_hash = hashlib.sha256(
            self.original.encode()
        ).hexdigest()
        session.proposed_hash = hashlib.sha256(
            proposed.encode()
        ).hexdigest()
        result = self.service.validator.static_validate(
            session,
            original=self.original,
            proposed=proposed,
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["checks"]["transform_exact"])
        self.assertFalse(result["checks"]["goal_aligned"])


if __name__ == "__main__":
    unittest.main()
