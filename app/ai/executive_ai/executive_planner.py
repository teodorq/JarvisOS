from __future__ import annotations

from typing import Any
from uuid import uuid4


class ExecutivePlanner:

    STRATEGY_ANALYZE = "ANALYZE"
    STRATEGY_IMPROVE = "IMPROVE"
    STRATEGY_EVOLVE = "EVOLVE"
    STRATEGY_STABILIZE = "STABILIZE"
    STRATEGY_EXPAND = "EXPAND"
    STRATEGY_OPTIMIZE = "OPTIMIZE"
    STRATEGY_NONE = "NONE"

    MODULE_PROJECT_DIRECTOR = "PROJECT_DIRECTOR"
    MODULE_REASONER = "REASONER"
    MODULE_RESEARCH = "RESEARCH"
    MODULE_SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    MODULE_EVOLUTION = "EVOLUTION"
    MODULE_CONTINUOUS_DEV = "CONTINUOUS_DEV"

    def build_plan(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
        mode: str = "SAFE_AUTONOMOUS",
        max_phases: int = 5,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "ExecutivePlanner wymaga objective."
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

        delegated_module = self.select_module(
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
            delegated_module=delegated_module,
            analysis=analysis,
            mode=mode,
            context=normalized_context,
        )

        roadmap = self._build_roadmap(
            strategy=strategy,
            delegated_module=delegated_module,
            priority=priority,
            analysis=analysis,
        )

        return {
            "plan_id": f"executive-plan-{uuid4().hex[:12]}",
            "objective": normalized_objective,
            "mode": str(
                mode
            ).strip().upper(),
            "max_phases": max(
                1,
                int(
                    max_phases
                ),
            ),
            "analysis": analysis,
            "selected_strategy": strategy,
            "delegated_module": delegated_module,
            "priority": priority,
            "risk": risk,
            "roadmap": roadmap,
            "can_execute": (
                strategy != self.STRATEGY_NONE
                and delegated_module
                != ""
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

        signals: list[str] = []
        categories: list[str] = []

        if self._contains_any(
            lowered,
            (
                "analizuj",
                "przeanalizuj",
                "sprawdź",
                "sprawdz",
                "zbadaj",
                "research",
                "raport",
            ),
        ):
            categories.append(
                self.STRATEGY_ANALYZE
            )
            signals.append(
                "Wykryto potrzebę analizy strategicznej."
            )

        if self._contains_any(
            lowered,
            (
                "ulepsz",
                "popraw jakość",
                "popraw jakosc",
                "self improvement",
                "samodoskonalenie",
            ),
        ):
            categories.append(
                self.STRATEGY_IMPROVE
            )
            signals.append(
                "Wykryto potrzebę ulepszenia projektu."
            )

        if self._contains_any(
            lowered,
            (
                "ewolucja",
                "evolution",
                "rozwijaj projekt",
                "długoterminowo",
                "dlugoterminowo",
                "wiele iteracji",
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
                "nie działa",
                "nie dziala",
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
                "dodaj moduł",
                "dodaj modul",
                "nowa funkcja",
                "rozszerz",
                "skaluj",
            ),
        ):
            categories.append(
                self.STRATEGY_EXPAND
            )
            signals.append(
                "Wykryto potrzebę rozbudowy projektu."
            )

        if self._contains_any(
            lowered,
            (
                "optymalizuj",
                "optymalizacja",
                "przyspiesz",
                "wydajność",
                "wydajnosc",
                "zużycie pamięci",
                "zuzycie pamieci",
            ),
        ):
            categories.append(
                self.STRATEGY_OPTIMIZE
            )
            signals.append(
                "Wykryto potrzebę optymalizacji."
            )

        if not categories:
            categories.append(
                self.STRATEGY_ANALYZE
            )
            signals.append(
                "Brak jednoznacznej strategii; "
                "wymagana analiza."
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
            "requires_project_change": any(
                category
                in {
                    self.STRATEGY_IMPROVE,
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
            self.STRATEGY_IMPROVE,
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
            self.STRATEGY_IMPROVE,
            self.STRATEGY_EVOLVE,
            self.STRATEGY_EXPAND,
            self.STRATEGY_OPTIMIZE,
            self.STRATEGY_ANALYZE,
        )

        for strategy in order:
            if strategy in categories:
                return strategy

        return self.STRATEGY_NONE

    def select_module(
        self,
        strategy: str,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        normalized_context = self._safe_dict(
            context
        )

        forced_module = str(
            normalized_context.get(
                "forced_module",
                "",
            )
        ).strip().upper()

        valid_modules = {
            self.MODULE_PROJECT_DIRECTOR,
            self.MODULE_REASONER,
            self.MODULE_RESEARCH,
            self.MODULE_SELF_IMPROVEMENT,
            self.MODULE_EVOLUTION,
            self.MODULE_CONTINUOUS_DEV,
        }

        if forced_module in valid_modules:
            return forced_module

        mapping = {
            self.STRATEGY_ANALYZE: self.MODULE_PROJECT_DIRECTOR,
            self.STRATEGY_IMPROVE: self.MODULE_PROJECT_DIRECTOR,
            self.STRATEGY_EVOLVE: self.MODULE_PROJECT_DIRECTOR,
            self.STRATEGY_STABILIZE: self.MODULE_PROJECT_DIRECTOR,
            self.STRATEGY_EXPAND: self.MODULE_PROJECT_DIRECTOR,
            self.STRATEGY_OPTIMIZE: self.MODULE_PROJECT_DIRECTOR,
        }

        selected = mapping.get(
            strategy,
            self.MODULE_PROJECT_DIRECTOR,
        )

        scope = str(
            analysis.get(
                "scope",
                "PROJECT",
            )
        ).upper()

        if scope == "LOCAL":
            if strategy == self.STRATEGY_ANALYZE:
                return self.MODULE_RESEARCH

            if strategy == self.STRATEGY_IMPROVE:
                return self.MODULE_SELF_IMPROVEMENT

            if strategy == self.STRATEGY_EVOLVE:
                return self.MODULE_EVOLUTION

            if strategy in {
                self.STRATEGY_STABILIZE,
                self.STRATEGY_EXPAND,
                self.STRATEGY_OPTIMIZE,
            }:
                return self.MODULE_CONTINUOUS_DEV

        return selected

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
                "PROJECT",
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
        delegated_module: str,
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
                "PROJECT",
            )
        ).upper()

        risk_score = 0.15
        reasons: list[str] = []

        if strategy in {
            self.STRATEGY_IMPROVE,
            self.STRATEGY_EVOLVE,
            self.STRATEGY_STABILIZE,
            self.STRATEGY_EXPAND,
            self.STRATEGY_OPTIMIZE,
        }:
            risk_score += 0.2
            reasons.append(
                "Strategia może prowadzić do zmian w projekcie."
            )

        if delegated_module in {
            self.MODULE_PROJECT_DIRECTOR,
            self.MODULE_SELF_IMPROVEMENT,
            self.MODULE_EVOLUTION,
            self.MODULE_CONTINUOUS_DEV,
        }:
            risk_score += 0.15
            reasons.append(
                "Delegowany moduł może wykonywać zmiany."
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
                and delegated_module
                in {
                    self.MODULE_PROJECT_DIRECTOR,
                    self.MODULE_EVOLUTION,
                    self.MODULE_CONTINUOUS_DEV,
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
        delegated_module: str,
        priority: str,
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:

        roadmap = [
            {
                "name": "ANALYZE_EXECUTIVE_OBJECTIVE",
                "module": "EXECUTIVE_AI",
                "description": (
                    "Przeanalizować cel strategiczny."
                ),
                "priority": priority,
            },
            {
                "name": "SELECT_STRATEGY",
                "module": "EXECUTIVE_AI",
                "description": (
                    "Wybrać najlepszą strategię działania."
                ),
                "priority": priority,
            },
            {
                "name": "ASSESS_RISK",
                "module": "EXECUTIVE_AI",
                "description": (
                    "Ocenić ryzyko i potrzebę akceptacji."
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
                    "name": "STRATEGIC_RESEARCH",
                    "module": self.MODULE_RESEARCH,
                    "description": (
                        "Zebrać dane wspierające decyzję."
                    ),
                    "priority": priority,
                }
            )

        roadmap.append(
            {
                "name": "DELEGATE_OBJECTIVE",
                "module": delegated_module,
                "description": (
                    "Delegować cel do wybranego modułu."
                ),
                "priority": priority,
            }
        )

        roadmap.append(
            {
                "name": "VALIDATE_EXECUTIVE_RESULT",
                "module": "EXECUTIVE_AI",
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
                "cały projekt",
                "caly projekt",
                "architektura",
                "wiele modułów",
                "wiele modulow",
                "długoterminowo",
                "dlugoterminowo",
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
