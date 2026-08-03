from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerRule:
    source_prefix: str
    forbidden_target_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class LayerViolation:
    source_module: str
    target_module: str
    source_layer: str
    forbidden_layer: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "source_layer": self.source_layer,
            "forbidden_layer": self.forbidden_layer,
        }


class LayerViolationDetector:

    DEFAULT_RULES = (
        LayerRule(
            source_prefix="app.core",
            forbidden_target_prefixes=(
                "app.gui",
                "app.desktop",
                "app.browser",
                "app.voice",
            ),
        ),
        LayerRule(
            source_prefix="app.memory",
            forbidden_target_prefixes=(
                "app.gui",
                "app.desktop",
                "app.browser",
            ),
        ),
        LayerRule(
            source_prefix="app.autodev",
            forbidden_target_prefixes=(
                "app.gui",
            ),
        ),
    )

    def __init__(
        self,
        rules: tuple[LayerRule, ...] | None = None,
    ) -> None:
        self.rules = rules or self.DEFAULT_RULES

    def detect(
        self,
        graph: dict[str, set[str]],
    ) -> list[LayerViolation]:
        violations: list[LayerViolation] = []

        for source_module, dependencies in graph.items():
            for rule in self.rules:
                if not self._matches_prefix(
                    source_module,
                    rule.source_prefix,
                ):
                    continue

                for target_module in dependencies:
                    for forbidden in rule.forbidden_target_prefixes:
                        if self._matches_prefix(
                            target_module,
                            forbidden,
                        ):
                            violations.append(
                                LayerViolation(
                                    source_module=source_module,
                                    target_module=target_module,
                                    source_layer=rule.source_prefix,
                                    forbidden_layer=forbidden,
                                )
                            )

        return sorted(
            violations,
            key=lambda item: (
                item.source_module,
                item.target_module,
            ),
        )

    @staticmethod
    def _matches_prefix(
        module: str,
        prefix: str,
    ) -> bool:
        return module == prefix or module.startswith(
            f"{prefix}."
        )
