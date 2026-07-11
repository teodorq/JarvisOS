from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.autodev.safe_patch_builder import SafePatch
from app.autodev.safe_patch_validator import (
    PatchValidationResult,
    SafePatchValidator,
)


@dataclass(slots=True)
class SafePatchExecutionPolicy:
    project_root: str = "C:/JarvisAI"
    backup_root: str = "data/autodev/safe_patch_backups"
    dry_run: bool = True
    require_approval: bool = True
    run_py_compile: bool = True
    run_unit_tests: bool = True
    unit_test_timeout_seconds: int = 120
    auto_rollback: bool = True


@dataclass(slots=True)
class PatchExecutionResult:
    success: bool
    status: str
    message: str
    patch_id: str = ""
    backup_path: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    compile_output: str = ""
    test_output: str = ""
    rolled_back: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafePatchExecutor:
    """
    Bezpieczny wykonawca patchy.

    Domyślnie działa w dry-run.
    Zapis następuje wyłącznie gdy:
    - patch przeszedł walidację,
    - approved=True,
    - policy.dry_run=False.
    """

    def __init__(
        self,
        policy: SafePatchExecutionPolicy | None = None,
        validator: SafePatchValidator | None = None,
    ) -> None:
        self.policy = (
            policy
            or SafePatchExecutionPolicy()
        )

        self.project_root = Path(
            self.policy.project_root
        ).resolve()

        self.backup_root = (
            self.project_root
            / self.policy.backup_root
        ).resolve()

        self.validator = (
            validator
            or SafePatchValidator(
                project_root=str(self.project_root)
            )
        )

        self.last_result: PatchExecutionResult | None = None

    def execute(
        self,
        patch: SafePatch,
        *,
        approved: bool = False,
    ) -> PatchExecutionResult:
        validation = self.validator.validate(
            patch
        )

        if not validation.success:
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="VALIDATION_FAILED",
                    message=(
                        "Patch nie przeszedł walidacji."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation.to_dict(),
                    errors=list(validation.errors),
                )
            )

        if (
            self.policy.require_approval
            and not approved
        ):
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="WAITING_FOR_APPROVAL",
                    message=(
                        "Patch jest poprawny, ale czeka "
                        "na akceptację."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation.to_dict(),
                )
            )

        if self.policy.dry_run:
            return self._finish(
                PatchExecutionResult(
                    success=True,
                    status="DRY_RUN_OK",
                    message=(
                        "Patch przeszedł walidację. "
                        "Dry-run nie zmienił pliku."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation.to_dict(),
                )
            )

        file_path = Path(
            patch.path
        ).resolve()

        current_content = file_path.read_text(
            encoding="utf-8"
        )

        current_hash = self._hash(
            current_content
        )

        if current_hash != patch.old_hash:
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="SOURCE_CHANGED",
                    message=(
                        "Plik zmienił się od czasu "
                        "utworzenia patcha."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation.to_dict(),
                    errors=[
                        "Hash bieżącego pliku nie pasuje."
                    ],
                )
            )

        backup_path = self._create_backup(
            file_path=file_path,
            patch_id=patch.patch_id,
        )

        try:
            self._atomic_write(
                file_path=file_path,
                content=patch.new_content,
            )

            compile_output = ""

            if self.policy.run_py_compile:
                compile_output = self._run_compile(
                    file_path
                )

            test_output = ""

            if self.policy.run_unit_tests:
                test_output = self._run_tests()

            return self._finish(
                PatchExecutionResult(
                    success=True,
                    status="COMPLETED",
                    message=(
                        "Patch zapisano i zweryfikowano."
                    ),
                    patch_id=patch.patch_id,
                    backup_path=str(backup_path),
                    validation=validation.to_dict(),
                    compile_output=compile_output,
                    test_output=test_output,
                )
            )

        except Exception as error:
            rolled_back = False

            if self.policy.auto_rollback:
                rolled_back = self._restore_backup(
                    backup_path=backup_path,
                    target_path=file_path,
                )

            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status=(
                        "FAILED_AND_ROLLED_BACK"
                        if rolled_back
                        else "FAILED"
                    ),
                    message=(
                        "Wykonanie patcha nie powiodło się."
                    ),
                    patch_id=patch.patch_id,
                    backup_path=str(backup_path),
                    validation=validation.to_dict(),
                    rolled_back=rolled_back,
                    errors=[
                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    ],
                )
            )

    def _create_backup(
        self,
        *,
        file_path: Path,
        patch_id: str,
    ) -> Path:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_dir = (
            self.backup_root
            / f"{timestamp}_{patch_id}"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        backup_path = (
            backup_dir
            / file_path.name
        )

        shutil.copy2(
            file_path,
            backup_path,
        )

        return backup_path

    def _atomic_write(
        self,
        *,
        file_path: Path,
        content: str,
    ) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(file_path.parent),
            suffix=".tmp",
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)

        temp_path.replace(file_path)

    def _run_compile(
        self,
        file_path: Path,
    ) -> str:
        result = subprocess.run(
            [
                "python",
                "-m",
                "py_compile",
                str(file_path),
            ],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr
                or "py_compile zakończył się błędem."
            )

        return (
            result.stdout.strip()
            or "PY_COMPILE_OK"
        )

    def _run_tests(
        self,
    ) -> str:
        result = subprocess.run(
            [
                "python",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=(
                self.policy.unit_test_timeout_seconds
            ),
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        if result.returncode != 0:
            raise RuntimeError(
                output
                or "Testy zakończyły się błędem."
            )

        return output

    def _restore_backup(
        self,
        *,
        backup_path: Path,
        target_path: Path,
    ) -> bool:
        try:
            shutil.copy2(
                backup_path,
                target_path,
            )
            return True
        except Exception:
            return False

    def _hash(
        self,
        content: str,
    ) -> str:
        return hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    def _finish(
        self,
        result: PatchExecutionResult,
    ) -> PatchExecutionResult:
        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "policy": asdict(self.policy),
            "project_root": str(self.project_root),
            "backup_root": str(self.backup_root),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
