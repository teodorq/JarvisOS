from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
import re
from typing import Any

from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)
from app.autodev.safe_patch_builder import SafePatch


@dataclass(slots=True)
class PatchValidationResult:
    success: bool
    status: str
    errors: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    checks: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafePatchValidator:
    """Validates a patch before approval or execution."""

    DANGEROUS_PATTERNS = (
        (
            r"\beval\s*\(",
            "Wykryto eval().",
        ),
        (
            r"\bexec\s*\(",
            "Wykryto exec().",
        ),
        (
            r"\bos\.system\s*\(",
            "Wykryto os.system().",
        ),
        (
            r"\bsubprocess\.(run|Popen|call)\s*\([^)]*"
            r"shell\s*=\s*True",
            "Wykryto subprocess z shell=True.",
        ),
        (
            r"\bshutil\.rmtree\s*\(",
            "Wykryto shutil.rmtree().",
        ),
        (
            r"\bos\.(remove|unlink)\s*\(",
            "Wykryto usuwanie pliku przez os.",
        ),
        (
            r"\.(unlink|rmdir)\s*\(",
            "Wykryto usuwanie przez pathlib.",
        ),
        (
            r"\bsocket\.",
            "Wykryto bezpośrednią obsługę socket.",
        ),
        (
            r"\brequests\.(post|put|patch|delete)\s*\(",
            "Wykryto operację sieciową modyfikującą dane.",
        ),
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        max_changed_lines: int = 500,
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        if max_changed_lines < 1:
            raise ValueError(
                "max_changed_lines musi być większe od zera."
            )

        self.policy = (
            policy
            or ExecutionPolicy(
                project_root=project_root,
            )
        )
        self.project_root = self.policy.root
        self.boundary = ProjectBoundaryPolicy(
            self.policy
        )
        self.max_changed_lines = int(
            max_changed_lines
        )
        self.last_result: (
            PatchValidationResult | None
        ) = None

    def validate(
        self,
        patch: SafePatch,
    ) -> PatchValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, Any] = {}

        try:
            file_path = self.boundary.resolve_target(
                patch.path,
                require_file=True,
                allow_missing=False,
            )
            checks["inside_project"] = True
            checks["path_safe"] = True
        except Exception as error:
            file_path = Path(
                patch.path
            )
            checks["inside_project"] = False
            checks["path_safe"] = False
            errors.append(
                str(error)
            )

        checks["python_file"] = (
            file_path.suffix.casefold()
            == ".py"
        )

        if not checks["python_file"]:
            errors.append(
                "Dozwolone są wyłącznie pliki Python."
            )

        computed_changed_lines = (
            self._count_changed_lines(
                patch.old_content,
                patch.new_content,
            )
        )
        checks["changed_lines"] = (
            patch.changed_lines
        )
        checks["changed_lines_match"] = (
            patch.changed_lines
            == computed_changed_lines
        )

        if (
            patch.changed_lines < 1
            or patch.changed_lines
            > self.max_changed_lines
        ):
            errors.append(
                "Patch przekracza dozwolony limit "
                "zmienionych linii."
            )

        if not checks["changed_lines_match"]:
            errors.append(
                "Liczba zmienionych linii nie zgadza się "
                "z zawartością patcha."
            )

        checks["content_changed"] = (
            patch.old_content
            != patch.new_content
        )

        if not checks["content_changed"]:
            errors.append(
                "Patch nie zawiera rzeczywistej zmiany."
            )

        old_hash = self._hash(
            patch.old_content
        )
        new_hash = self._hash(
            patch.new_content
        )
        checks["old_hash_valid"] = (
            old_hash == patch.old_hash
        )
        checks["new_hash_valid"] = (
            new_hash == patch.new_hash
        )

        if not checks["old_hash_valid"]:
            errors.append(
                "old_hash nie pasuje do old_content."
            )

        if not checks["new_hash_valid"]:
            errors.append(
                "new_hash nie pasuje do new_content."
            )

        if checks["path_safe"]:
            try:
                current_content = file_path.read_text(
                    encoding="utf-8"
                )
                checks["source_unchanged"] = (
                    self._hash(
                        current_content
                    )
                    == patch.old_hash
                )

                if not checks["source_unchanged"]:
                    errors.append(
                        "Plik źródłowy zmienił się po "
                        "utworzeniu patcha."
                    )
            except (
                OSError,
                UnicodeError,
            ) as error:
                checks["source_unchanged"] = False
                errors.append(
                    f"Nie można odczytać targetu: {error}"
                )

        syntax_error = self._syntax_error(
            patch.new_content,
            file_path,
        )
        checks["syntax_ok"] = (
            syntax_error is None
        )

        if syntax_error is not None:
            errors.append(
                syntax_error
            )

        dangerous_hits = (
            self._find_dangerous_patterns(
                patch.new_content
            )
        )
        checks["dangerous_patterns"] = (
            dangerous_hits
        )

        if dangerous_hits:
            errors.extend(
                dangerous_hits
            )

        if "\x00" in patch.new_content:
            errors.append(
                "Kod zawiera niedozwolony znak NUL."
            )

        if "except Exception" in patch.new_content:
            warnings.append(
                "Kod nadal zawiera szerokie except Exception."
            )

        if "TODO" in patch.new_content.upper():
            warnings.append(
                "Kod zawiera TODO."
            )

        if patch.requires_approval is not True:
            warnings.append(
                "Patch nie deklaruje wymogu akceptacji; "
                "wykonawca i tak wymusi approval gate."
            )

        result = PatchValidationResult(
            success=not errors,
            status=(
                "VALID"
                if not errors
                else "REJECTED"
            ),
            errors=self._unique(
                errors
            ),
            warnings=self._unique(
                warnings
            ),
            checks=checks,
        )
        self.last_result = result
        return result

    def _syntax_error(
        self,
        content: str,
        path: Path,
    ) -> str | None:
        try:
            ast.parse(
                content,
                filename=str(path),
            )
            return None
        except SyntaxError as error:
            return (
                "Błąd składni: "
                f"linia {error.lineno or 0}, "
                f"{error.msg}"
            )

    def _find_dangerous_patterns(
        self,
        content: str,
    ) -> list[str]:
        hits: list[str] = []

        for pattern, message in self.DANGEROUS_PATTERNS:
            if re.search(
                pattern,
                content,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            ):
                hits.append(
                    message
                )

        try:
            tree = ast.parse(
                content
            )
        except SyntaxError:
            return self._unique(
                hits
            )

        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            name = self._call_name(
                node.func
            )

            if name in {
                "eval",
                "exec",
                "os.system",
                "shutil.rmtree",
                "os.remove",
                "os.unlink",
            }:
                hits.append(
                    f"Wykryto niedozwolone wywołanie: {name}()."
                )

            if name in {
                "subprocess.run",
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
            }:
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(
                            keyword.value,
                            ast.Constant,
                        )
                        and keyword.value.value is True
                    ):
                        hits.append(
                            "Wykryto subprocess z shell=True."
                        )

        return self._unique(
            hits
        )

    @staticmethod
    def _call_name(
        node: ast.AST,
    ) -> str:
        parts: list[str] = []
        current = node

        while isinstance(
            current,
            ast.Attribute,
        ):
            parts.append(
                current.attr
            )
            current = current.value

        if isinstance(
            current,
            ast.Name,
        ):
            parts.append(
                current.id
            )

        return ".".join(
            reversed(parts)
        )

    @staticmethod
    def _hash(
        content: str,
    ) -> str:
        return hashlib.sha256(
            content.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _count_changed_lines(
        old_content: str,
        new_content: str,
    ) -> int:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        maximum = max(
            len(old_lines),
            len(new_lines),
        )

        return sum(
            1
            for index in range(maximum)
            if (
                (
                    old_lines[index]
                    if index < len(old_lines)
                    else None
                )
                != (
                    new_lines[index]
                    if index < len(new_lines)
                    else None
                )
            )
        )

    @staticmethod
    def _unique(
        values: list[str],
    ) -> list[str]:
        return list(
            dict.fromkeys(
                value
                for value in values
                if value
            )
        )

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "project_root": str(
                self.project_root
            ),
            "max_changed_lines": (
                self.max_changed_lines
            ),
            "policy": self.policy.to_dict(),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
