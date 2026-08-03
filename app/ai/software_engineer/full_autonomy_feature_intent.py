from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Any

from .feature_code_generator import FeatureCodeGenerator
from .feature_planner import FeaturePlanner


class FullAutonomyFeatureIntent:
    """Builds an executable new-feature plan from a natural-language goal."""

    CREATE_WORDS = (
        "utwórz",
        "utworz",
        "stwórz",
        "stworz",
        "zbuduj",
        "dodaj",
        "create",
        "build",
        "add",
    )
    MODULE_WORDS = (
        "moduł",
        "modul",
        "pakiet",
        "package",
        "module",
        "feature",
        "funkcjonalność",
        "funkcjonalnosc",
    )
    EXISTING_CHANGE_MARKERS = (
        "dla istniejącego modułu",
        "dla istniejacego modulu",
        "existing module",
        "zachowaj publiczne api",
        "preserve public api",
        "refaktoryz",
        "podziel zbyt",
        "napraw",
        "popraw",
    )

    def __init__(
        self,
        project_root: str | Path,
        *,
        planner: FeaturePlanner | None = None,
        generator: FeatureCodeGenerator | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(
            strict=False
        )
        self.planner = planner or FeaturePlanner()
        self.generator = generator or FeatureCodeGenerator()

    def detect(
        self,
        objective: str,
        *,
        allow_existing: bool = False,
    ) -> dict[str, Any] | None:
        normalized = " ".join(str(objective).split()).strip()
        lowered = normalized.casefold()

        if self._is_existing_file_change(normalized, lowered):
            return None

        if not (
            any(word in lowered for word in self.CREATE_WORDS)
            and any(word in lowered for word in self.MODULE_WORDS)
        ):
            return None

        package_path = self._package_path(normalized)

        if not package_path:
            return None

        feature_name = self._feature_name(package_path)
        include_repository = any(
            word in lowered
            for word in (
                "repozytor",
                "repository",
                "magazyn danych",
            )
        )
        include_controller = any(
            word in lowered
            for word in (
                "kontroler",
                "controller",
            )
        )

        blueprint = self.planner.plan(
            normalized,
            feature_name=feature_name,
            package_path=package_path,
            include_controller=include_controller,
            include_repository=include_repository,
        )
        replacements = self.generator.generate(
            blueprint
        )
        targets = list(replacements)

        existing = [
            path
            for path in targets
            if (self.project_root / path).exists()
        ]

        if existing and not allow_existing:
            raise ValueError(
                "Pełna autonomia nie nadpisze istniejącego "
                "modułu bez jawnej zgody: "
                + ", ".join(existing)
            )

        campaigns = self._campaigns(
            normalized,
            feature_name=feature_name,
            package_path=package_path,
            replacements=replacements,
            blueprint=blueprint.to_dict(),
        )

        return {
            "feature_name": feature_name,
            "package_path": package_path,
            "target_files": targets,
            "replacements": replacements,
            "campaigns": campaigns,
            "blueprint": blueprint.to_dict(),
            "allow_existing": bool(allow_existing),
            "planning_source": "new_feature_intent",
        }

    @classmethod
    def _is_existing_file_change(
        cls,
        objective: str,
        lowered: str,
    ) -> bool:
        if not any(
            marker in lowered
            for marker in cls.EXISTING_CHANGE_MARKERS
        ):
            return False

        matches = re.findall(
            r"(?<![A-Za-z0-9_])"
            r"(app[\\/][A-Za-z0-9_.\-/\\]+)",
            str(objective),
            flags=re.IGNORECASE,
        )
        if not matches:
            return False

        raw = matches[0].replace("\\", "/").rstrip(
            ".,;:)]}"
        )
        return bool(PurePosixPath(raw).suffix)

    @classmethod
    def _package_path(
        cls,
        objective: str,
    ) -> str:
        matches = re.findall(
            r"(?<![A-Za-z0-9_])"
            r"(app[\\/][A-Za-z0-9_.\-/\\]+)",
            str(objective),
            flags=re.IGNORECASE,
        )

        if not matches:
            return ""

        raw = matches[0].replace("\\", "/").rstrip(
            ".,;:)]}"
        )
        path = PurePosixPath(raw)

        if (
            path.is_absolute()
            or ".." in path.parts
            or len(path.parts) < 2
            or path.parts[0].casefold() != "app"
        ):
            raise ValueError(
                "Niebezpieczna ścieżka nowego modułu."
            )

        if path.suffix:
            raise ValueError(
                "Podaj katalog modułu, nie pojedynczy plik."
            )

        normalized = path.as_posix()

        if normalized.casefold().startswith(
            (
                "app/archive/",
                "app/data/",
                "app/ai_pliki/",
            )
        ):
            raise ValueError(
                "Wybrano chronioną ścieżkę modułu."
            )

        return normalized

    @staticmethod
    def _feature_name(
        package_path: str,
    ) -> str:
        leaf = PurePosixPath(package_path).name
        words = re.findall(
            r"[A-Za-z0-9]+",
            leaf,
        )
        return "".join(
            word[:1].upper() + word[1:]
            for word in words
        ) or "GeneratedFeature"

    @staticmethod
    def _campaigns(
        objective: str,
        *,
        feature_name: str,
        package_path: str,
        replacements: dict[str, str],
        blueprint: dict[str, Any],
    ) -> list[dict[str, Any]]:
        targets = list(replacements)
        test_targets = [
            path
            for path in targets
            if path.startswith("tests/")
        ]
        implementation_targets = [
            path
            for path in targets
            if path not in test_targets
        ]
        create_stage = "autonomy-feature-create"
        syntax_stage = "autonomy-feature-syntax"
        tests_stage = "autonomy-feature-tests"
        full_stage = "autonomy-feature-full-validation"

        return [
            {
                "campaign_id": "autonomy-01-feature-foundation",
                "objective": (
                    f"{objective} — utworzenie modułu {feature_name}."
                ),
                "priority": "CRITICAL",
                "depends_on": [],
                "estimated_roi": 9.2,
                "estimated_risk": 3.2,
                "estimated_minutes": max(
                    45,
                    len(targets) * 12,
                ),
                "confidence": 0.91,
                "stages": [
                    {
                        "stage_id": create_stage,
                        "objective": (
                            f"Utwórz atomowo moduł {package_path} "
                            "wraz z testami."
                        ),
                        "targets": targets,
                        "replacements": dict(replacements),
                        "allow_same_subsystem": True,
                        "metadata": {
                            "execution_kind": "feature_creation",
                            "feature_name": feature_name,
                            "package_path": package_path,
                            "include_repository": (
                                "repository.py"
                                in {
                                    PurePosixPath(path).name
                                    for path in targets
                                }
                            ),
                            "include_controller": (
                                "controller.py"
                                in {
                                    PurePosixPath(path).name
                                    for path in targets
                                }
                            ),
                            "allow_existing": False,
                            "feature_blueprint": dict(blueprint),
                        },
                    },
                    {
                        "stage_id": syntax_stage,
                        "objective": (
                            "Zweryfikuj składnię i kompletność "
                            "nowo utworzonych plików."
                        ),
                        "targets": targets,
                        "depends_on": [create_stage],
                        "allow_same_subsystem": True,
                        "metadata": {
                            "execution_kind": "validation_only",
                            "full_suite": False,
                            "validation_scope": "changed_files",
                        },
                    },
                ],
                "metadata": {
                    "full_autonomy": True,
                    "phase": "feature_foundation",
                    "execution_kind": "feature_creation",
                },
            },
            {
                "campaign_id": "autonomy-02-feature-delivery",
                "objective": (
                    f"{objective} — niezależna walidacja modułu "
                    f"{feature_name}."
                ),
                "priority": "HIGH",
                "depends_on": [
                    "autonomy-01-feature-foundation",
                ],
                "estimated_roi": 8.6,
                "estimated_risk": 1.8,
                "estimated_minutes": 35,
                "confidence": 0.94,
                "stages": [
                    {
                        "stage_id": tests_stage,
                        "objective": (
                            "Uruchom testy nowej funkcjonalności."
                        ),
                        "targets": (
                            test_targets
                            + implementation_targets[:1]
                            if test_targets
                            else targets[:2]
                        ),
                        "allow_same_subsystem": True,
                        "metadata": {
                            "execution_kind": "validation_only",
                            "full_suite": False,
                            "validation_scope": "changed_files",
                        },
                    },
                    {
                        "stage_id": full_stage,
                        "objective": (
                            "Uruchom pełną regresję projektu "
                            "i potwierdź brak zmian poza planem."
                        ),
                        "targets": targets,
                        "depends_on": [tests_stage],
                        "allow_same_subsystem": True,
                        "metadata": {
                            "execution_kind": "validation_only",
                            "full_suite": True,
                            "validation_scope": "project",
                        },
                    },
                ],
                "metadata": {
                    "full_autonomy": True,
                    "phase": "feature_delivery",
                    "execution_kind": "validation_only",
                },
            },
        ]
