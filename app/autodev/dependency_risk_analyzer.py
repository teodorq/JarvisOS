from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.autodev.project_scanner import ProjectScanner


@dataclass(slots=True)
class DependencyRiskResult:
    success: bool
    status: str
    target: str = ""
    direct_dependents: list[str] = field(default_factory=list)
    direct_dependencies: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)
    dependency_count: int = 0
    dependent_count: int = 0
    risk_score: float = 0.0
    risk_level: str = "LOW"
    reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DependencyRiskAnalyzer:
    """
    Analizuje ryzyko zależności dla pojedynczego modułu.

    Moduł:
    - nie zapisuje kodu,
    - nie wykonuje importów projektu,
    - korzysta wyłącznie z danych ze skanera AST.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:

        self.project_root = Path(
            project_root
        ).resolve()

        self.scanner = ProjectScanner(
            project_root=str(self.project_root)
        )

        self.last_result: DependencyRiskResult | None = None

    def analyze(
        self,
        target: str,
    ) -> DependencyRiskResult:

        target_path = self._resolve_target(
            target
        )

        scan_report = self.scanner.scan_with_report()
        project_index = scan_report["index"]

        files = list(
            getattr(
                project_index,
                "files",
                [],
            )
        )

        target_file = None

        for project_file in files:
            if Path(project_file.path).resolve() == target_path:
                target_file = project_file
                break

        if target_file is None:
            return self._finish(
                DependencyRiskResult(
                    success=False,
                    status="TARGET_NOT_FOUND",
                    target=str(target_path),
                    errors=[
                        "Nie znaleziono modułu w indeksie projektu."
                    ],
                )
            )

        module_name = self._module_name(
            target_path
        )

        direct_dependencies = sorted(
            {
                str(item).strip()
                for item in getattr(
                    target_file,
                    "imports",
                    [],
                )
                if str(item).strip()
            }
        )

        direct_dependents: list[str] = []

        for project_file in files:
            if Path(project_file.path).resolve() == target_path:
                continue

            imports = {
                str(item).strip()
                for item in getattr(
                    project_file,
                    "imports",
                    [],
                )
                if str(item).strip()
            }

            if self._imports_target(
                imports=imports,
                module_name=module_name,
            ):
                direct_dependents.append(
                    str(project_file.path)
                )

        direct_dependents.sort()

        affected_modules = sorted(
            {
                str(target_path),
                *direct_dependents,
            }
        )

        risk_score, reasons = self._calculate_risk(
            dependency_count=len(direct_dependencies),
            dependent_count=len(direct_dependents),
            line_count=int(
                getattr(
                    target_file,
                    "line_count",
                    0,
                )
                or 0
            ),
        )

        result = DependencyRiskResult(
            success=True,
            status="DEPENDENCY_RISK_READY",
            target=str(target_path),
            direct_dependents=direct_dependents,
            direct_dependencies=direct_dependencies,
            affected_modules=affected_modules,
            dependency_count=len(direct_dependencies),
            dependent_count=len(direct_dependents),
            risk_score=risk_score,
            risk_level=self._risk_level(risk_score),
            reasons=reasons,
        )

        return self._finish(
            result
        )

    def _resolve_target(
        self,
        target: str,
    ) -> Path:

        candidate = Path(
            str(target).strip()
        )

        if not candidate.is_absolute():
            candidate = self.project_root / candidate

        resolved = candidate.resolve()

        try:
            resolved.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Target znajduje się poza projektem."
            ) from error

        return resolved

    def _module_name(
        self,
        path: Path,
    ) -> str:

        relative = path.relative_to(
            self.project_root
        )

        without_suffix = relative.with_suffix("")

        return ".".join(
            without_suffix.parts
        )

    def _imports_target(
        self,
        *,
        imports: set[str],
        module_name: str,
    ) -> bool:

        for imported in imports:
            if (
                imported == module_name
                or imported.startswith(
                    module_name + "."
                )
                or module_name.startswith(
                    imported + "."
                )
            ):
                return True

        return False

    def _calculate_risk(
        self,
        *,
        dependency_count: int,
        dependent_count: int,
        line_count: int,
    ) -> tuple[float, list[str]]:

        score = 0.0
        reasons: list[str] = []

        if dependency_count > 10:
            score += 20.0
            reasons.append(
                "Moduł ma wiele zależności wejściowych."
            )

        if dependency_count > 20:
            score += 15.0

        if dependent_count > 3:
            score += 25.0
            reasons.append(
                "Wiele modułów zależy od tego pliku."
            )

        if dependent_count > 10:
            score += 20.0

        if line_count > 500:
            score += 15.0
            reasons.append(
                "Moduł jest duży."
            )

        if line_count > 1000:
            score += 5.0

        if not reasons:
            reasons.append(
                "Nie wykryto podwyższonego ryzyka zależności."
            )

        return min(
            round(score, 2),
            100.0,
        ), reasons

    def _risk_level(
        self,
        score: float,
    ) -> str:

        if score >= 70:
            return "CRITICAL"

        if score >= 45:
            return "HIGH"

        if score >= 20:
            return "MEDIUM"

        return "LOW"

    def _finish(
        self,
        result: DependencyRiskResult,
    ) -> DependencyRiskResult:

        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": str(self.project_root),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
