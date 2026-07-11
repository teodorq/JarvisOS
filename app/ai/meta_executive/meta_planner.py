from __future__ import annotations

from typing import Any
from uuid import uuid4


class MetaPlanner:

    STRATEGY_ANALYZE = "ANALYZE"
    STRATEGY_GOVERN = "GOVERN"
    STRATEGY_EVOLVE = "EVOLVE"
    STRATEGY_STABILIZE = "STABILIZE"
    STRATEGY_EXPAND = "EXPAND"
    STRATEGY_OPTIMIZE = "OPTIMIZE"
    STRATEGY_NONE = "NONE"

    LAYER_EXECUTIVE_AI = "EXECUTIVE_AI"
    LAYER_PROJECT_DIRECTOR = "PROJECT_DIRECTOR"
    LAYER_SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    LAYER_EVOLUTION = "EVOLUTION"
    LAYER_CONTINUOUS_DEV = "CONTINUOUS_DEV"
    LAYER_REASONER = "REASONER"
    LAYER_RESEARCH = "RESEARCH"

    def build_plan(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
        mode: str = "SAFE_AUTONOMOUS",
        max_cycles: int = 5,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "MetaPlanner wymaga objective."
            )

        normalized_context = self._safe_dict(
            context
        )

        analysis = self.analyze_objective(
            objective=normalized_objective,
            context=normalized_context,
        )

        strategy = self.select_strategy(
            analysis=analysis,
            context=normalized_context,
        )

        selected_layer = self.select_layer(
            strategy=strategy,
            analysis=analysis,
            context=normalized_context,
        )

        priority = self.determine_priority(
            analysis=analysis,
            context=normalized_context,
        )

        risk = self.assess_risk(
            strategy=strategy,
            selected_layer=selected_layer,
            analysis=analysis,
            mode=mode,
            context=normalized_context,
        )

        roadmap = self._build_roadmap(
            strategy=strategy,
            selected_layer=selected_layer,
            priority=priority,
            analysis=analysis,
        )

        return {
            "plan_id": f"meta-plan-{uuid4().hex[:12]}",
            "objective": normalized_objective,
            "mode": str(
                mode
            ).strip().upper(),
            "max_cycles": max(
                1,
                int(
                    max_cycles
                ),
            ),
            "analysis": analysis,
            "selected_strategy": strategy,
            "selected_layer": selected_layer,
            "priority": priority,
            "risk": risk,
            "roadmap": roadmap,
            "can_execute": (
                strategy != self.STRATEGY_NONE
                and selected_layer != ""
            ),
        }

    def analyze_objective(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        text = str(
            objective
        ).strip()

        lowered = text.lower()
        normalized_context = self._safe_dict(
            context
        )

        categories: list[str] = []
        signals: list[str] = []

        if self._contains_any(
            lowered,
            (
                "analizuj",
                "przeanalizuj",
                "zbadaj",
                "raport",
                "research",
            ),
        ):
            categories.append(
                self.STRATEGY_ANALYZE
            )
            signals.append(
                "Wykryto potrzebę analizy systemowej."
            )

        if self._contains_any(
            lowered,
            (
                "zarządzaj",
                "zarzadzaj",
                "koordynuj",
                "ustal priorytety",
                "roadmapa",
                "strategia całego systemu",
                "strategia calego systemu",
            ),
        ):
            categories.append(
                self.STRATEGY_GOVERN
            )
            signals.append(
                "Wykryto potrzebę zarządzania całym systemem."
            )

        if self._contains_any(
            lowered,
            (
                "ewolucja",
                "evolution",
                "rozwijaj cały system",
                "rozwijaj caly system",
                "długoterminowy rozwój",
                "dlugoterminowy rozwoj",
            ),
        ):
            categories.append(
                self.STRATEGY_EVOLVE
            )
            signals.append(
                "Wykryto potrzebę rozwoju ewolucyjnego."
            )

        if self._contains_any(
            lowered,
            (
                "stabilność",
                "stabilnosc",
                "napraw błędy",
                "napraw bledy",
                "awaria",
                "bezpieczeństwo",
                "bezpieczenstwo",
            ),
        ):
            categories.append(
                self.STRATEGY_STABILIZE
            )
            signals.append(
                "Wykryto potrzebę stabilizacji systemu."
            )

        if self._contains_any(
            lowered,
            (
                "rozbuduj",
                "dodaj moduły",
                "dodaj moduly",
                "skaluj",
                "rozszerz",
            ),
        ):
            categories.append(
                self.STRATEGY_EXPAND
            )
            signals.append(
                "Wykryto potrzebę rozbudowy systemu."
            )

        if self._contains_any(
            lowered,
            (
                "optymalizuj",
                "optymalizacja",
                "przyspiesz",
                "wydajność",
                "wydajnosc",
            ),
        ):
            categories.append(
                self.STRATEGY_OPTIMIZE
            )
            signals.append(
                "Wykryto potrzebę optymalizacji systemu."
            )

        if not categories:
            categories.append(
                self.STRATEGY_GOVERN
            )
            signals.append(
                "Brak jednoznacznej kategorii; "
                "wybrano zarządzanie nadrzędne."
            )

        complexity = self._estimate_complexity(
            lowered
        )

        urgency = self._estimate_urgency(
            lowered,
            normalized_context,
        )

        scope = self._estimate_scope(
            lowered
        )

        return {
            "objective": text,
            "categories": categories,
            "signals": signals,
            "complexity": complexity,
            "urgency": urgency,
            "scope": scope,
            "requires_change": any(
                category
                in {
                    self.STRATEGY_EVOLVE,
                    self.STRATEGY_STABILIZE,
                    self.STRATEGY_EXPAND,
                    self.STRATEGY_OPTIMIZE,
                }
                for category in categories
            ),
            "requires_research": (
                self.STRATEGY_ANALYZE
                in categories
            ),
        }

    def select_strategy(
        self,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        normalized_context = self._safe_dict(
            context
        )

        forced_strategy = str(
            normalized_context.get(
                "forced_strategy",
                "",
            )
        ).strip().upper()

        valid = {
            self.STRATEGY_ANALYZE,
            self.STRATEGY_GOVERN,
            self.STRATEGY_EVOLVE,
            self.STRATEGY_STABILIZE,
            self.STRATEGY_EXPAND,
            self.STRATEGY_OPTIMIZE,
        }

        if forced_strategy in valid:
            return forced_strategy

        categories = self._safe_string_list(
            analysis.get(
                "categories",
                [],
            )
        )

        order = (
            self.STRATEGY_STABILIZE,
            self.STRATEGY_GOVERN,
            self.STRATEGY_EVOLVE,
            self.STRATEGY_EXPAND,
            self.STRATEGY_OPTIMIZE,
            self.STRATEGY_ANALYZE,
        )

        for strategy in order:
            if strategy in categories:
                return strategy

        return self.STRATEGY_NONE

    def select_layer(
        self,
        strategy: str,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        normalized_context = self._safe_dict(
            context
        )

        forced_layer = str(
            normalized_context.get(
                "forced_layer",
                "",
            )
        ).strip().upper()

        valid_layers = {
            self.LAYER_EXECUTIVE_AI,
            self.LAYER_PROJECT_DIRECTOR,
            self.LAYER_SELF_IMPROVEMENT,
            self.LAYER_EVOLUTION,
            self.LAYER_CONTINUOUS_DEV,
            self.LAYER_REASONER,
            self.LAYER_RESEARCH,
        }

        if forced_layer in valid_layers:
            return forced_layer

        scope = str(
            analysis.get(
                "scope",
                "SYSTEM",
            )
        ).upper()

        if scope == "SYSTEM":
            return self.LAYER_EXECUTIVE_AI

        if scope == "PROJECT":
            return self.LAYER_PROJECT_DIRECTOR

        mapping = {
            self.STRATEGY_ANALYZE: self.LAYER_RESEARCH,
            self.STRATEGY_GOVERN: self.LAYER_EXECUTIVE_AI,
            self.STRATEGY_EVOLVE: self.LAYER_EVOLUTION,
            self.STRATEGY_STABILIZE: self.LAYER_CONTINUOUS_DEV,
            self.STRATEGY_EXPAND: self.LAYER_PROJECT_DIRECTOR,
            self.STRATEGY_OPTIMIZE: self.LAYER_SELF_IMPROVEMENT,
        }

        return mapping.get(
            strategy,
            self.LAYER_EXECUTIVE_AI,
        )

    def determine_priority(
        self,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        normalized_context = self._safe_dict(
            context
        )

        explicit = str(
            normalized_context.get(
                "priority",
                "",
            )
        ).strip().upper()

        if explicit in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }:
            return explicit

        urgency = str(
            analysis.get(
                "urgency",
                "MEDIUM",
            )
        ).upper()

        complexity = str(
            analysis.get(
                "complexity",
                "MEDIUM",
            )
        ).upper()

        scope = str(
            analysis.get(
                "scope",
                "SYSTEM",
            )
        ).upper()

        if urgency == "CRITICAL":
            return "CRITICAL"

        if urgency == "HIGH":
            return "HIGH"

        if complexity == "HIGH":
            return "HIGH"

        if scope == "SYSTEM":
            return "HIGH"

        if urgency == "LOW":
            return "LOW"

        return "MEDIUM"

    def assess_risk(
        self,
        strategy: str,
        selected_layer: str,
        analysis: dict[str, Any],
        mode: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_mode = str(
            mode
        ).strip().upper()

        normalized_context = self._safe_dict(
            context
        )

        destructive = bool(
            normalized_context.get(
                "destructive",
                False,
            )
        )

        production = bool(
            normalized_context.get(
                "production",
                False,
            )
        )

        complexity = str(
            analysis.get(
                "complexity",
                "MEDIUM",
            )
        ).upper()

        scope = str(
            analysis.get(
                "scope",
                "SYSTEM",
            )
        ).upper()

        risk_score = 0.2
        reasons: list[str] = []

        if strategy in {
            self.STRATEGY_EVOLVE,
            self.STRATEGY_STABILIZE,
            self.STRATEGY_EXPAND,
            self.STRATEGY_OPTIMIZE,
        }:
            risk_score += 0.2
            reasons.append(
                "Strategia może zmienić system."
            )

        if selected_layer in {
            self.LAYER_EXECUTIVE_AI,
            self.LAYER_PROJECT_DIRECTOR,
            self.LAYER_EVOLUTION,
            self.LAYER_CONTINUOUS_DEV,
        }:
            risk_score += 0.15
            reasons.append(
                "Wybrana warstwa może wykonywać zmiany."
            )

        if complexity == "HIGH":
            risk_score += 0.2
            reasons.append(
                "Cel ma wysoką złożoność."
            )

        if scope == "SYSTEM":
            risk_score += 0.15
            reasons.append(
                "Cel obejmuje cały system."
            )

        if destructive:
            risk_score += 0.3
            reasons.append(
                "Operacja została oznaczona jako destrukcyjna."
            )

        if production:
            risk_score += 0.15
            reasons.append(
                "Operacja dotyczy środowiska produkcyjnego."
            )

        risk_score = min(
            1.0,
            risk_score,
        )

        if risk_score >= 0.8:
            risk_level = "CRITICAL"
        elif risk_score >= 0.6:
            risk_level = "HIGH"
        elif risk_score >= 0.35:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        requires_approval = (
            normalized_mode == "MANUAL"
            or risk_level in {
                "HIGH",
                "CRITICAL",
            }
            or (
                normalized_mode == "SAFE_AUTONOMOUS"
                and selected_layer
                in {
                    self.LAYER_EXECUTIVE_AI,
                    self.LAYER_PROJECT_DIRECTOR,
                    self.LAYER_EVOLUTION,
                    self.LAYER_CONTINUOUS_DEV,
                }
            )
        )

        return {
            "risk_level": risk_level,
            "risk_score": round(
                risk_score,
                2,
            ),
            "requires_approval": requires_approval,
            "reasons": reasons,
        }

    def _build_roadmap(
        self,
        strategy: str,
        selected_layer: str,
        priority: str,
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:

        roadmap = [
            {
                "name": "ANALYZE_META_OBJECTIVE",
                "layer": "META_EXECUTIVE",
                "description": (
                    "Przeanalizować cel nadrzędny."
                ),
                "priority": priority,
            },
            {
                "name": "SELECT_META_STRATEGY",
                "layer": "META_EXECUTIVE",
                "description": (
                    "Wybrać strategię nadrzędną."
                ),
                "priority": priority,
            },
            {
                "name": "SELECT_EXECUTION_LAYER",
                "layer": "META_EXECUTIVE",
                "description": (
                    "Wybrać warstwę wykonawczą."
                ),
                "priority": priority,
            },
        ]

        if analysis.get(
            "requires_research",
            False,
        ):
            roadmap.append(
                {
                    "name": "META_RESEARCH",
                    "layer": self.LAYER_RESEARCH,
                    "description": (
                        "Zebrać dane do decyzji nadrzędnej."
                    ),
                    "priority": priority,
                }
            )

        roadmap.append(
            {
                "name": "DELEGATE_META_OBJECTIVE",
                "layer": selected_layer,
                "description": (
                    "Delegować cel do wybranej warstwy."
                ),
                "priority": priority,
            }
        )

        roadmap.append(
            {
                "name": "VALIDATE_META_RESULT",
                "layer": "META_EXECUTIVE",
                "description": (
                    "Zweryfikować wynik i zapisać wnioski."
                ),
                "priority": priority,
            }
        )

        return roadmap

    def _estimate_complexity(
        self,
        text: str,
    ) -> str:

        if self._contains_any(
            text,
            (
                "cały system",
                "caly system",
                "jarvis os",
                "wszystkie moduły",
                "wszystkie moduly",
                "architektura",
                "długoterminowy",
                "dlugoterminowy",
            ),
        ):
            return "HIGH"

        if self._contains_any(
            text,
            (
                "status",
                "summary",
                "lista",
                "pokaż",
                "pokaz",
            ),
        ):
            return "LOW"

        return "MEDIUM"

    def _estimate_urgency(
        self,
        text: str,
        context: dict[str, Any],
    ) -> str:

        explicit = str(
            context.get(
                "urgency",
                "",
            )
        ).strip().upper()

        if explicit in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }:
            return explicit

        if self._contains_any(
            text,
            (
                "krytyczne",
                "critical",
                "natychmiast",
                "awaria",
                "nie działa",
                "nie dziala",
            ),
        ):
            return "CRITICAL"

        if self._contains_any(
            text,
            (
                "pilne",
                "urgent",
                "ważne",
                "wazne",
            ),
        ):
            return "HIGH"

        return "MEDIUM"

    def _estimate_scope(
        self,
        text: str,
    ) -> str:

        if self._contains_any(
            text,
            (
                "cały system",
                "caly system",
                "jarvis os",
                "wszystkie moduły",
                "wszystkie moduly",
            ),
        ):
            return "SYSTEM"

        if self._contains_any(
            text,
            (
                "cały projekt",
                "caly projekt",
                "projekt",
                "architektura",
            ),
        ):
            return "PROJECT"

        return "LOCAL"

    def _contains_any(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:

        return any(
            phrase in text
            for phrase in phrases
        )

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (list, tuple, set),
        ):
            return []

        return [
            str(
                item
            ).strip().upper()
            for item in value
            if str(
                item
            ).strip()
        ]
