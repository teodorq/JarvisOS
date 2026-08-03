from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
from typing import Any

from app.autodev.execution_guard import (
    ExecutionGuard,
)
from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)
from app.autodev.safe_patch_builder import SafePatch
from app.autodev.safe_patch_validator import (
    SafePatchValidator,
)
from app.core.safe_process import SafeProcessRunner


@dataclass(slots=True)
class SafePatchExecutionPolicy:
    project_root: str | Path | None = None
    backup_root: str = (
        "data/autodev/safe_patch_backups"
    )
    dry_run: bool = True
    require_approval: bool = True
    run_py_compile: bool = True
    run_unit_tests: bool = True
    unit_test_timeout_seconds: int = 120
    auto_rollback: bool = True
    max_risk_score: float = 65.0
    max_auto_approval_risk: float = 20.0
    allow_auto_approval: bool = False


@dataclass(slots=True)
class PatchExecutionResult:
    success: bool
    status: str
    message: str
    patch_id: str = ""
    backup_path: str = ""
    validation: dict[str, Any] = field(
        default_factory=dict
    )
    guard: dict[str, Any] = field(
        default_factory=dict
    )
    compile_output: str = ""
    test_output: str = ""
    rolled_back: bool = False
    errors: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafePatchExecutor:
    """Executes an approved patch inside project boundaries."""

    def __init__(
        self,
        policy: SafePatchExecutionPolicy | None = None,
        validator: SafePatchValidator | None = None,
        guard: ExecutionGuard | None = None,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:
        self.policy = (
            policy
            or SafePatchExecutionPolicy()
        )
        self.execution_policy = ExecutionPolicy(
            project_root=self.policy.project_root,
            max_risk_score=(
                self.policy.max_risk_score
            ),
            max_auto_approval_risk=(
                self.policy.max_auto_approval_risk
            ),
            allow_auto_approval=(
                self.policy.allow_auto_approval
            ),
        )
        self.project_root = (
            self.execution_policy.root
        )
        self.boundary = ProjectBoundaryPolicy(
            self.execution_policy
        )
        self.backup_root = (
            self._resolve_backup_root(
                self.policy.backup_root
            )
        )
        self.validator = (
            validator
            or SafePatchValidator(
                policy=self.execution_policy
            )
        )
        self.guard = (
            guard
            or ExecutionGuard(
                policy=self.execution_policy
            )
        )
        self.python_executable = str(
            Path(
                sys.executable
            ).resolve(
                strict=False
            )
        )
        self.unit_test_timeout = min(
            600,
            max(
                1,
                int(
                    self.policy.unit_test_timeout_seconds
                ),
            ),
        )
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=self.project_root,
                allowed_executables=[
                    self.python_executable,
                ],
                max_timeout_seconds=max(
                    30,
                    self.unit_test_timeout,
                ),
                max_output_chars=12000,
            )
        )
        self.last_result: (
            PatchExecutionResult | None
        ) = None

    def execute(
        self,
        patch: SafePatch,
        *,
        approved: bool = False,
        automatic_approval: bool = False,
    ) -> PatchExecutionResult:
        validation = self.validator.validate(
            patch
        )
        validation_data = validation.to_dict()

        if not validation.success:
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="VALIDATION_FAILED",
                    message=(
                        "Patch nie przeszedł walidacji."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation_data,
                    errors=list(
                        validation.errors
                    ),
                )
            )

        prediction = {
            "risk_score": patch.metadata.get(
                "risk_score",
                0.0,
            ),
            "risk_level": patch.metadata.get(
                "risk_level",
                "LOW",
            ),
        }
        decision = self.guard.evaluate(
            task={
                "target": patch.path,
            },
            prediction=prediction,
            validation=validation_data,
            approved=approved,
            automatic=automatic_approval,
        )
        guard_data = decision.to_dict()

        if not decision.allowed:
            status = decision.status

            if status == "EXECUTION_BLOCKED":
                message = (
                    "Polityka bezpieczeństwa zablokowała "
                    "wykonanie patcha."
                )
            else:
                message = (
                    "Patch jest poprawny, ale czeka "
                    "na jawną akceptację."
                )

            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status=status,
                    message=message,
                    patch_id=patch.patch_id,
                    validation=validation_data,
                    guard=guard_data,
                    errors=list(
                        decision.errors
                    ),
                )
            )

        if self.policy.dry_run:
            return self._finish(
                PatchExecutionResult(
                    success=True,
                    status="DRY_RUN_OK",
                    message=(
                        "Patch przeszedł walidację i "
                        "approval gate. Dry-run nie "
                        "zmienił pliku."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation_data,
                    guard=guard_data,
                )
            )

        try:
            file_path = (
                self.boundary.resolve_target(
                    patch.path,
                    require_file=True,
                    allow_missing=False,
                )
            )
            current_content = (
                file_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as error:
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="TARGET_REJECTED",
                    message=(
                        "Target nie przeszedł ponownej "
                        "walidacji przed zapisem."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation_data,
                    guard=guard_data,
                    errors=[
                        str(error),
                    ],
                )
            )

        current_hash = self._hash(
            current_content
        )

        if (
            current_hash != patch.old_hash
            or self._hash(
                patch.old_content
            )
            != patch.old_hash
        ):
            return self._finish(
                PatchExecutionResult(
                    success=False,
                    status="SOURCE_CHANGED",
                    message=(
                        "Plik zmienił się od czasu "
                        "utworzenia patcha."
                    ),
                    patch_id=patch.patch_id,
                    validation=validation_data,
                    guard=guard_data,
                    errors=[
                        "Hash bieżącego pliku nie pasuje.",
                    ],
                )
            )

        backup_path = self._create_backup(
            file_path=file_path,
            patch_id=patch.patch_id,
        )

        try:
            # Final TOCTOU check immediately before write.
            file_path = (
                self.boundary.resolve_target(
                    file_path,
                    require_file=True,
                    allow_missing=False,
                )
            )

            if self._hash(
                file_path.read_text(
                    encoding="utf-8"
                )
            ) != patch.old_hash:
                raise RuntimeError(
                    "Target zmienił się bezpośrednio "
                    "przed zapisem."
                )

            self._atomic_write(
                file_path=file_path,
                content=patch.new_content,
            )

            if self._hash(
                file_path.read_text(
                    encoding="utf-8"
                )
            ) != patch.new_hash:
                raise RuntimeError(
                    "Weryfikacja zapisanego pliku "
                    "nie powiodła się."
                )

            compile_output = ""

            if self.policy.run_py_compile:
                compile_output = (
                    self._run_compile(
                        file_path
                    )
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
                    backup_path=str(
                        backup_path
                    ),
                    validation=validation_data,
                    guard=guard_data,
                    compile_output=compile_output,
                    test_output=test_output,
                )
            )

        except Exception as error:
            rolled_back = False

            if self.policy.auto_rollback:
                rolled_back = (
                    self._restore_backup(
                        backup_path=backup_path,
                        target_path=file_path,
                    )
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
                    backup_path=str(
                        backup_path
                    ),
                    validation=validation_data,
                    guard=guard_data,
                    rolled_back=rolled_back,
                    errors=[
                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                    ],
                )
            )

    def _resolve_backup_root(
        self,
        value: str | Path,
    ) -> Path:
        candidate = Path(
            value
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                self.project_root
                / candidate
            )

        resolved = candidate.resolve(
            strict=False
        )

        try:
            relative = resolved.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Katalog backupu znajduje się poza "
                "projektem."
            ) from error

        if (
            not relative.parts
            or relative.parts[0].casefold()
            not in {
                "data",
                ".jarvis",
            }
        ):
            raise ValueError(
                "Backup musi znajdować się w katalogu "
                "data lub .jarvis projektu."
            )

        current = self.project_root

        for part in relative.parts:
            current = current / part

            if current.exists() and current.is_symlink():
                raise ValueError(
                    "Katalog backupu zawiera symlink."
                )

        return resolved

    def _create_backup(
        self,
        *,
        file_path: Path,
        patch_id: str,
    ) -> Path:
        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%S"
        )
        safe_patch_id = "".join(
            character
            for character in str(
                patch_id
            )
            if character.isalnum()
            or character in {
                "-",
                "_",
            }
        )[:64]

        if not safe_patch_id:
            raise ValueError(
                "Nieprawidłowy patch_id."
            )

        backup_dir = (
            self.backup_root
            / f"{timestamp}_{safe_patch_id}"
        )
        backup_dir.mkdir(
            parents=True,
            exist_ok=False,
        )
        backup_path = (
            backup_dir
            / file_path.name
        )
        shutil.copy2(
            file_path,
            backup_path,
        )

        if self._hash(
            backup_path.read_text(
                encoding="utf-8"
            )
        ) != self._hash(
            file_path.read_text(
                encoding="utf-8"
            )
        ):
            raise RuntimeError(
                "Weryfikacja backupu nie powiodła się."
            )

        return backup_path

    def _atomic_write(
        self,
        *,
        file_path: Path,
        content: str,
    ) -> None:
        temporary_path: Path | None = None
        mode = stat.S_IMODE(
            file_path.stat().st_mode
        )

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=str(
                    file_path.parent
                ),
                prefix=(
                    f".{file_path.name}."
                ),
                suffix=".tmp",
            ) as handle:
                handle.write(
                    content
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )
                temporary_path = Path(
                    handle.name
                )

            os.chmod(
                temporary_path,
                mode,
            )
            self._replace_with_retry(
                temporary_path,
                file_path,
            )
            temporary_path = None
        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                try:
                    temporary_path.unlink()
                except OSError:
                    raise RuntimeError("AutoDev: przechwycony wyjątek")

    def _run_compile(
        self,
        file_path: Path,
    ) -> str:
        result = self.process_runner.run(
            [
                self.python_executable,
                "-m",
                "py_compile",
                str(file_path),
            ],
            cwd=self.project_root,
            timeout=30,
        )

        if not result.success:
            raise RuntimeError(
                result.stderr
                or result.stdout
                or "py_compile zakończył się błędem."
            )

        return (
            result.stdout.strip()
            or "PY_COMPILE_OK"
        )

    def _run_tests(
        self,
    ) -> str:
        result = self.process_runner.run(
            [
                self.python_executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ],
            cwd=self.project_root,
            timeout=self.unit_test_timeout,
        )
        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        if not result.success:
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
            target = (
                self.boundary.resolve_target(
                    target_path,
                    require_file=True,
                    allow_missing=False,
                )
            )
            content = backup_path.read_text(
                encoding="utf-8"
            )
            self._atomic_write(
                file_path=target,
                content=content,
            )
            return (
                self._hash(
                    target.read_text(
                        encoding="utf-8"
                    )
                )
                == self._hash(
                    content
                )
            )
        except Exception:
            return False

    @staticmethod
    def _replace_with_retry(
        source: Path,
        destination: Path,
        *,
        attempts: int = 6,
    ) -> None:
        last_error: OSError | None = None

        for attempt in range(
            max(
                1,
                attempts,
            )
        ):
            try:
                if destination.exists():
                    try:
                        mode = stat.S_IMODE(
                            destination.stat().st_mode
                        )
                        os.chmod(
                            destination,
                            mode | stat.S_IWRITE,
                        )
                    except OSError:
                        raise RuntimeError("AutoDev: przechwycony wyjątek")

                os.replace(
                    source,
                    destination,
                )
                return
            except OSError as error:
                last_error = error

                if attempt + 1 >= attempts:
                    break

                time.sleep(
                    0.02
                    * (attempt + 1)
                )

        if last_error is not None:
            raise last_error

    @staticmethod
    def _hash(
        content: str,
    ) -> str:
        return hashlib.sha256(
            content.encode(
                "utf-8"
            )
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
            "policy": asdict(
                self.policy
            ),
            "execution_policy": (
                self.execution_policy.to_dict()
            ),
            "project_root": str(
                self.project_root
            ),
            "backup_root": str(
                self.backup_root
            ),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
