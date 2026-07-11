from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.autodev.safe_patch_builder import SafePatch


@dataclass(slots=True)
class PatchValidationResult:
    success: bool
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafePatchValidator:
    """
    Waliduje patch przed wykonaniem.

    Blokuje między innymi:
    - zapis poza projektem,
    - pliki inne niż Python,
    - błędy składni,
    - eval/exec,
    - subprocess z shell=True,
    - os.system,
    - próby usuwania katalogów,
    - podejrzane operacje sieciowe.
    """

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
            r"\bsubprocess\.(run|Popen|call)\s*\([^)]*shell\s*=\s*True",
            "Wykryto subprocess z shell=True.",
        ),
        (
            r"\bshutil\.rmtree\s*\(",
            "Wykryto shutil.rmtree().",
        ),
        (
            r"\bos\.remove\s*\(",
            "Wykryto os.remove().",
        ),
        (
            r"\bos\.unlink\s*\(",
            "Wykryto os.unlink().",
        ),
        (
            r"\bsocket\.",
            "Wykryto bezpośrednią obsługę socket.",
        ),
        (
            r"\brequests\.(post|put|delete)\s*\(",
            "Wykryto operację sieciową modyfikującą dane.",
        ),
    )

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        max_changed_lines: int = 500,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.max_changed_lines = max_changed_lines
        self.last_result: PatchValidationResult | None = None

    def validate(
        self,
        patch: SafePatch,
    ) -> PatchValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, Any] = {}

        file_path = Path(patch.path).resolve()

        try:
            file_path.relative_to(self.project_root)
            checks["inside_project"] = True
        except ValueError:
            checks["inside_project"] = False
            errors.append(
                "Patch wskazuje plik poza katalogiem projektu."
            )

        checks["python_file"] = (
            file_path.suffix.casefold() == ".py"
        )

        if not checks["python_file"]:
            errors.append(
                "Dozwolone są wyłącznie pliki Python."
            )

        checks["changed_lines"] = patch.changed_lines

        if patch.changed_lines > self.max_changed_lines:
            errors.append(
                "Patch przekracza limit zmienionych linii."
            )

        checks["content_changed"] = (
            patch.old_content != patch.new_content
        )

        if not checks["content_changed"]:
            errors.append(
                "Patch nie zawiera rzeczywistej zmiany."
            )

        syntax_error = self._syntax_error(
            patch.new_content,
            file_path,
        )

        checks["syntax_ok"] = syntax_error is None

        if syntax_error is not None:
            errors.append(syntax_error)

        dangerous_hits = self._find_dangerous_patterns(
            patch.new_content
        )

        checks["dangerous_patterns"] = dangerous_hits

        if dangerous_hits:
            errors.extend(dangerous_hits)

        if "except Exception" in patch.new_content:
            warnings.append(
                "Kod nadal zawiera szerokie except Exception."
            )

        if "TODO" in patch.new_content.upper():
            warnings.append(
                "Kod zawiera TODO."
            )

        result = PatchValidationResult(
            success=not errors,
            status=(
                "VALID"
                if not errors
                else "REJECTED"
            ),
            errors=errors,
            warnings=warnings,
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
                flags=re.IGNORECASE | re.DOTALL,
            ):
                hits.append(message)

        return hits

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "max_changed_lines": self.max_changed_lines,
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
