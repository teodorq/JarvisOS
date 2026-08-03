from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSplitPlan:
    target: str
    reason: str
    proposed_modules: tuple[str, ...]
    migration_steps: tuple[str, ...]
    priority: str
    estimated_risk: float
    estimated_roi: float

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "reason": self.reason,
            "proposed_modules": list(self.proposed_modules),
            "migration_steps": list(self.migration_steps),
            "priority": self.priority,
            "estimated_risk": self.estimated_risk,
            "estimated_roi": self.estimated_roi,
        }


class ModuleSplitPlanner:

    def build_from_god_objects(
        self,
        god_objects: list[dict[str, object]],
    ) -> list[ModuleSplitPlan]:
        plans: list[ModuleSplitPlan] = []

        for item in god_objects:
            module = str(item["module"])
            class_name = str(item["class_name"])
            target = f"{module}.{class_name}"

            responsibilities = max(
                2,
                int(item.get("responsibility_count", 2)),
            )
            split_count = min(4, responsibilities)

            base_name = class_name.removesuffix("Controller")
            proposed_modules = tuple(
                f"{module.rsplit('.', 1)[0]}.{base_name.lower()}_{index + 1}"
                for index in range(split_count)
            )

            plans.append(
                ModuleSplitPlan(
                    target=target,
                    reason=(
                        "Klasa skupia zbyt wiele odpowiedzialności "
                        "i powinna zostać podzielona."
                    ),
                    proposed_modules=proposed_modules,
                    migration_steps=(
                        "Zidentyfikuj grupy odpowiedzialności.",
                        "Wyodrębnij interfejsy i zależności.",
                        "Przenieś metody do nowych modułów.",
                        "Dodaj testy regresyjne.",
                        "Usuń nieużywany kod po migracji.",
                    ),
                    priority="high",
                    estimated_risk=0.55,
                    estimated_roi=0.82,
                )
            )

        return plans

    def build_from_large_files(
        self,
        large_files: dict[str, int],
    ) -> list[ModuleSplitPlan]:
        plans: list[ModuleSplitPlan] = []

        for file_path, line_count in sorted(
            large_files.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            stem = file_path.replace("\\", "/").rsplit("/", 1)[-1]
            stem = stem.rsplit(".", 1)[0]

            plans.append(
                ModuleSplitPlan(
                    target=file_path,
                    reason=(
                        f"Plik ma {line_count} linii i przekracza "
                        "zalecany rozmiar."
                    ),
                    proposed_modules=(
                        f"{stem}_service",
                        f"{stem}_models",
                        f"{stem}_helpers",
                    ),
                    migration_steps=(
                        "Podziel kod według odpowiedzialności.",
                        "Przenieś modele i dane do osobnego modułu.",
                        "Przenieś logikę pomocniczą do helpers.",
                        "Zachowaj kompatybilny interfejs publiczny.",
                        "Uruchom pełny zestaw testów.",
                    ),
                    priority="medium",
                    estimated_risk=0.40,
                    estimated_roi=0.70,
                )
            )

        return plans
