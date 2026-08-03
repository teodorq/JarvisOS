from __future__ import annotations

import re
from pathlib import PurePosixPath

from .feature_dependency_planner import (
    FeatureDependencyPlanner,
)
from .feature_models import (
    FeatureBlueprint,
    FeatureFileSpec,
)


class FeaturePlanner:

    def __init__(self) -> None:
        self.dependencies = (
            FeatureDependencyPlanner()
        )

    def plan(
        self,
        objective: str,
        *,
        feature_name: str | None = None,
        package_path: str | None = None,
        include_controller: bool = True,
        include_repository: bool = False,
    ) -> FeatureBlueprint:
        normalized_objective = " ".join(
            str(objective).split()
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "Cel funkcjonalności nie może być pusty."
            )

        resolved_name = (
            self._feature_name(
                normalized_objective,
                feature_name,
            )
        )
        slug = self._slug(
            resolved_name
        )
        resolved_package = self._package_path(
            slug=slug,
            package_path=package_path,
        )

        files = self._build_files(
            objective=normalized_objective,
            feature_name=resolved_name,
            slug=slug,
            package_path=resolved_package,
            include_controller=include_controller,
            include_repository=include_repository,
        )

        self.dependencies.validate(
            files
        )
        creation_order = (
            self.dependencies.creation_order(
                files
            )
        )

        rollback_scope = [
            item.relative_path
            for item in files
            if item.required
        ]
        validation_targets = [
            item.relative_path
            for item in files
            if item.category == "test"
        ]

        implementation_count = sum(
            item.category != "test"
            for item in files
        )
        estimated_risk = round(
            min(
                0.85,
                0.24
                + implementation_count * 0.055
                + (
                    0.08
                    if include_repository
                    else 0.0
                ),
            ),
            3,
        )
        estimated_roi = round(
            min(
                0.98,
                0.70
                + implementation_count * 0.035,
            ),
            3,
        )

        return FeatureBlueprint(
            feature_name=resolved_name,
            feature_slug=slug,
            objective=normalized_objective,
            package_path=resolved_package,
            files=files,
            creation_order=creation_order,
            validation_targets=validation_targets,
            rollback_scope=rollback_scope,
            estimated_roi=estimated_roi,
            estimated_risk=estimated_risk,
            metadata={
                "source": "feature_planner",
                "multi_file": True,
                "include_controller": (
                    include_controller
                ),
                "include_repository": (
                    include_repository
                ),
            },
        )

    def _build_files(
        self,
        *,
        objective: str,
        feature_name: str,
        slug: str,
        package_path: str,
        include_controller: bool,
        include_repository: bool,
    ) -> list[FeatureFileSpec]:
        files = [
            FeatureFileSpec(
                file_id="models",
                relative_path=(
                    f"{package_path}/models.py"
                ),
                purpose=(
                    "Modele danych i kontrakty "
                    f"dla {feature_name}."
                ),
                category="model",
                acceptance_criteria=[
                    "Modele mają jawne typy.",
                    "Modele nie zależą od warstwy UI.",
                ],
                metadata={
                    "objective": objective,
                },
            ),
            FeatureFileSpec(
                file_id="service",
                relative_path=(
                    f"{package_path}/service.py"
                ),
                purpose=(
                    "Główna logika biznesowa "
                    f"funkcjonalności {feature_name}."
                ),
                category="service",
                dependencies=[
                    "models",
                ],
                integration_points=[
                    "app.ai.brain",
                ],
                acceptance_criteria=[
                    "Logika jest oddzielona od UI.",
                    "Błędy mają jednoznaczne statusy.",
                ],
                metadata={
                    "objective": objective,
                },
            ),
        ]

        if include_repository:
            files.append(
                FeatureFileSpec(
                    file_id="repository",
                    relative_path=(
                        f"{package_path}/repository.py"
                    ),
                    purpose=(
                        "Warstwa zapisu i odczytu danych "
                        f"dla {feature_name}."
                    ),
                    category="repository",
                    dependencies=[
                        "models",
                    ],
                    acceptance_criteria=[
                        "Operacje danych są izolowane.",
                        "Błędy I/O są obsłużone.",
                    ],
                    metadata={
                        "objective": objective,
                    },
                )
            )
            service = next(
                item
                for item in files
                if item.file_id == "service"
            )
            service.dependencies.append(
                "repository"
            )

        public_dependencies = [
            "models",
            "service",
        ]

        if include_repository:
            public_dependencies.append(
                "repository"
            )

        if include_controller:
            files.append(
                FeatureFileSpec(
                    file_id="controller",
                    relative_path=(
                        f"{package_path}/controller.py"
                    ),
                    purpose=(
                        "Kontroler wejścia i integracji "
                        f"dla {feature_name}."
                    ),
                    category="controller",
                    dependencies=[
                        "service",
                    ],
                    integration_points=[
                        "app.ai.brain",
                        "app.ai.planner_llm",
                    ],
                    acceptance_criteria=[
                        "Kontroler waliduje wejście.",
                        "Kontroler nie zawiera logiki biznesowej.",
                    ],
                    metadata={
                        "objective": objective,
                    },
                )
            )
            public_dependencies.append(
                "controller"
            )

        files.append(
            FeatureFileSpec(
                file_id="package_init",
                relative_path=(
                    f"{package_path}/__init__.py"
                ),
                purpose=(
                    "Publiczny interfejs pakietu "
                    f"{feature_name}."
                ),
                category="package",
                dependencies=(
                    public_dependencies
                ),
                acceptance_criteria=[
                    "Eksportowane są tylko publiczne klasy.",
                ],
                metadata={
                    "objective": objective,
                },
            )
        )

        test_dependencies = [
            item.file_id
            for item in files
            if item.category != "test"
        ]

        files.append(
            FeatureFileSpec(
                file_id="tests",
                relative_path=(
                    f"tests/test_{slug}_feature.py"
                ),
                purpose=(
                    "Testy jednostkowe i integracyjne "
                    f"funkcjonalności {feature_name}."
                ),
                category="test",
                dependencies=(
                    test_dependencies
                ),
                integration_points=[
                    "unittest",
                ],
                acceptance_criteria=[
                    "Testy obejmują ścieżkę sukcesu.",
                    "Testy obejmują błędne dane.",
                    "Testy nie modyfikują prawdziwych danych.",
                ],
                metadata={
                    "objective": objective,
                    "test_target": package_path,
                },
            )
        )

        return files

    @classmethod
    def _feature_name(
        cls,
        objective: str,
        explicit_name: str | None,
    ) -> str:
        if explicit_name:
            cleaned = cls._pascal_case(
                explicit_name
            )

            if cleaned:
                return cleaned

        matches = re.findall(
            r"\b[A-Z][A-Za-z0-9_]{2,}\b",
            objective,
        )
        ignored = {
            "AI",
            "JARVIS",
            "OS",
            "API",
            "AutoDev",
        }

        for candidate in matches:
            if candidate not in ignored:
                return cls._pascal_case(
                    candidate
                )

        words = [
            word
            for word in re.findall(
                r"[A-Za-zÀ-ž0-9]+",
                objective,
            )
            if word.casefold()
            not in {
                "dodaj",
                "stwórz",
                "stworz",
                "zbuduj",
                "nowy",
                "nową",
                "nowa",
                "moduł",
                "modul",
                "system",
                "funkcję",
                "funkcje",
                "funkcjonalność",
                "funkcjonalnosc",
            }
        ]

        candidate = " ".join(
            words[:3]
        ) or "Generated Feature"

        return cls._pascal_case(
            candidate
        )

    @staticmethod
    def _pascal_case(
        value: str,
    ) -> str:
        words = re.findall(
            r"[A-Za-z0-9]+",
            str(value),
        )

        return "".join(
            word[:1].upper()
            + word[1:]
            for word in words
        ) or "GeneratedFeature"

    @staticmethod
    def _slug(
        value: str,
    ) -> str:
        expanded = re.sub(
            r"(?<!^)(?=[A-Z])",
            "_",
            value,
        )
        slug = re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            expanded,
        ).strip(
            "_"
        ).lower()

        return slug or "generated_feature"

    @staticmethod
    def _package_path(
        *,
        slug: str,
        package_path: str | None,
    ) -> str:
        raw = (
            str(package_path)
            if package_path
            else f"app/features/{slug}"
        )
        normalized = raw.replace(
            "\\",
            "/",
        ).strip(
            "/"
        )
        path = PurePosixPath(
            normalized
        )

        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
        ):
            raise ValueError(
                "Niebezpieczna ścieżka pakietu."
            )

        if path.parts[0] != "app":
            raise ValueError(
                "Pakiet funkcjonalności musi "
                "znajdować się w folderze app."
            )

        return path.as_posix()
