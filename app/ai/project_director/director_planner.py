from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.ai.planner.goal_decomposer import GoalDecomposer


class DirectorPlanner:

    def __init__(
        self,
        goal_decomposer: GoalDecomposer | None = None,
    ) -> None:
        self.goal_decomposer = (
            goal_decomposer
            if goal_decomposer is not None
            else GoalDecomposer()
        )

    MODULE_RESEARCH = "RESEARCH"
    MODULE_REASONER = "REASONER"
    MODULE_SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    MODULE_EVOLUTION = "EVOLUTION"
    MODULE_CONTINUOUS_DEV = "CONTINUOUS_DEV"
    MODULE_NONE = "NONE"

    def build_plan(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "DirectorPlanner wymaga objective."
            )

        normalized_context = self._safe_dict(
            context
        )

        analysis = self.analyze_objective(
            objective=normalized_objective,
            context=normalized_context,
        )

        selected_module = self.select_module(
            analysis=analysis,
            context=normalized_context,
        )

        priority = self.determine_priority(
            analysis=analysis,
            context=normalized_context,
        )

        risk = self.assess_risk(
            analysis=analysis,
            selected_module=selected_module,
            mode=mode,
            context=normalized_context,
        )

        decomposition = self._decompose_objective(
            objective=normalized_objective,
            analysis=analysis,
            priority=priority,
            context=normalized_context,
        )

        steps = self._build_steps(
            selected_module=selected_module,
            analysis=analysis,
            priority=priority,
            decomposition=decomposition,
        )

        return {
            "plan_id": f"director-plan-{uuid4().hex[:12]}",
            "objective": normalized_objective,
            "mode": str(
                mode
            ).strip().upper(),
            "max_iterations": max(
                1,
                int(
                    max_iterations
                ),
            ),
            "analysis": analysis,
            "selected_module": selected_module,
            "priority": priority,
            "risk": risk,
            "decomposition": decomposition,
            "steps": steps,
            "can_execute": (
                selected_module
                != self.MODULE_NONE
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

        research_words = (
            "zbadaj",
            "research",
            "przeanalizuj projekt",
            "sprawdź projekt",
            "sprawdz projekt",
            "znajdź problem",
            "znajdz problem",
            "raport",
            "analiza kodu",
        )

        reasoner_words = (
            "zdecyduj",
            "porównaj",
            "porownaj",
            "wybierz strategię",
            "wybierz strategie",
            "oceń opcje",
            "ocen opcje",
            "rozumowanie",
            "reasoner",
        )

        improvement_words = (
            "ulepsz siebie",
            "self improvement",
            "samodoskonalenie",
            "popraw jakość",
            "popraw jakosc",
            "popraw stabilność",
            "popraw stabilnosc",
            "napraw słabości",
            "napraw slabosci",
        )

        evolution_words = (
            "ewolucja",
            "evolution",
            "rozwijaj projekt",
            "autonomicznie rozwijaj",
            "długoterminowy rozwój",
            "dlugoterminowy rozwoj",
            "wiele iteracji",
        )

        continuous_words = (
            "continuous developer",
            "ciągły rozwój",
            "ciagly rozwoj",
            "wykonaj zmianę",
            "wykonaj zmiane",
            "napraw kod",
            "wdrożenie",
            "wdrozenie",
            "implementuj",
        )

        if self._contains_any(
            lowered,
            research_words,
        ):
            categories.append(
                self.MODULE_RESEARCH
            )
            signals.append(
                "Wykryto potrzebę analizy lub raportu."
            )

        if self._contains_any(
            lowered,
            reasoner_words,
        ):
            categories.append(
                self.MODULE_REASONER
            )
            signals.append(
                "Wykryto potrzebę wyboru strategii."
            )

        if self._contains_any(
            lowered,
            improvement_words,
        ):
            categories.append(
                self.MODULE_SELF_IMPROVEMENT
            )
            signals.append(
                "Wykryto cel samodoskonalenia."
            )

        if self._contains_any(
            lowered,
            evolution_words,
        ):
            categories.append(
                self.MODULE_EVOLUTION
            )
            signals.append(
                "Wykryto cel ewolucyjny."
            )

        if self._contains_any(
            lowered,
            continuous_words,
        ):
            categories.append(
                self.MODULE_CONTINUOUS_DEV
            )
            signals.append(
                "Wykryto potrzebę wykonania zmian."
            )

        if not categories:
            categories.append(
                self.MODULE_REASONER
            )
            signals.append(
                "Brak jednoznacznej kategorii; "
                "wymagane rozumowanie."
            )

        complexity = self._estimate_complexity(
            lowered
        )

        urgency = self._estimate_urgency(
            lowered,
            normalized_context,
        )

        return {
            "objective": text,
            "categories": categories,
            "signals": signals,
            "complexity": complexity,
            "urgency": urgency,
            "requires_code_change": (
                self.MODULE_CONTINUOUS_DEV
                in categories
                or self.MODULE_SELF_IMPROVEMENT
                in categories
                or self.MODULE_EVOLUTION
                in categories
            ),
            "requires_research": (
                self.MODULE_RESEARCH
                in categories
            ),
            "requires_strategy": (
                self.MODULE_REASONER
                in categories
            ),
        }

    def select_module(
        self,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        categories = self._safe_string_list(
            analysis.get(
                "categories",
                [],
            )
        )

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
            self.MODULE_RESEARCH,
            self.MODULE_REASONER,
            self.MODULE_SELF_IMPROVEMENT,
            self.MODULE_EVOLUTION,
            self.MODULE_CONTINUOUS_DEV,
        }

        if forced_module in valid_modules:
            return forced_module

        priority_order = (
            self.MODULE_SELF_IMPROVEMENT,
            self.MODULE_EVOLUTION,
            self.MODULE_CONTINUOUS_DEV,
            self.MODULE_RESEARCH,
            self.MODULE_REASONER,
        )

        for module_name in priority_order:
            if module_name in categories:
                return module_name

        return self.MODULE_NONE

    def determine_priority(
        self,
        analysis: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:

        normalized_context = self._safe_dict(
            context
        )

        explicit_priority = str(
            normalized_context.get(
                "priority",
                "",
            )
        ).strip().upper()

        if explicit_priority in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }:
            return explicit_priority

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

        if urgency == "CRITICAL":
            return "CRITICAL"

        if urgency == "HIGH":
            return "HIGH"

        if complexity == "HIGH":
            return "HIGH"

        if urgency == "LOW":
            return "LOW"

        return "MEDIUM"

    def assess_risk(
        self,
        analysis: dict[str, Any],
        selected_module: str,
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

        risk_score = 0.2
        reasons: list[str] = []

        if selected_module in {
            self.MODULE_SELF_IMPROVEMENT,
            self.MODULE_EVOLUTION,
            self.MODULE_CONTINUOUS_DEV,
        }:
            risk_score += 0.25
            reasons.append(
                "Moduł może modyfikować projekt."
            )

        if complexity == "HIGH":
            risk_score += 0.2
            reasons.append(
                "Cel ma wysoką złożoność."
            )

        if destructive:
            risk_score += 0.3
            reasons.append(
                "Kontekst oznaczono jako destrukcyjny."
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
                and selected_module
                in {
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

    def _decompose_objective(
        self,
        objective: str,
        analysis: dict[str, Any],
        priority: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        goal_type = (
            "PROJECT"
            if str(analysis.get("complexity", "")).upper() == "HIGH"
            else "FEATURE"
        )

        goal = {
            "title": objective,
            "description": objective,
            "goal_type": goal_type,
            "priority": priority,
            "timeframe": (
                "LONG_TERM"
                if str(analysis.get("complexity", "")).upper() == "HIGH"
                else "MEDIUM_TERM"
            ),
            "tags": self._safe_string_list(
                analysis.get("categories", [])
            ),
            "success_criteria": [
                "Wszystkie fazy planu zakończone",
                "Wynik końcowy przeszedł walidację",
            ],
        }

        decomposition_context = dict(context)
        decomposition_context.setdefault(
            "high_risk",
            str(analysis.get("urgency", "")).upper() == "CRITICAL",
        )

        try:
            return self.goal_decomposer.decompose(
                goal=goal,
                context=decomposition_context,
                max_subgoals=10,
            )
        except Exception as exc:
            return {
                "success": False,
                "status": "DECOMPOSITION_FAILED",
                "subgoals": [],
                "execution_order": [],
                "warnings": [
                    f"GoalDecomposer error: {type(exc).__name__}: {exc}"
                ],
            }

    def _build_steps(
        self,
        selected_module: str,
        analysis: dict[str, Any],
        priority: str,
        decomposition: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:

        steps = [
            {
                "name": "ANALYZE_OBJECTIVE",
                "module": "PROJECT_DIRECTOR",
                "description": (
                    "Przeanalizować cel i kontekst."
                ),
                "priority": priority,
            },
            {
                "name": "SELECT_MODULE",
                "module": "PROJECT_DIRECTOR",
                "description": (
                    "Wybrać najlepszy moduł wykonawczy."
                ),
                "priority": priority,
            },
        ]

        if analysis.get(
            "requires_research",
            False,
        ) and selected_module != self.MODULE_RESEARCH:
            steps.append(
                {
                    "name": "RESEARCH_SUPPORT",
                    "module": self.MODULE_RESEARCH,
                    "description": (
                        "Zebrać dane wspierające decyzję."
                    ),
                    "priority": priority,
                }
            )

        if analysis.get(
            "requires_strategy",
            False,
        ) and selected_module != self.MODULE_REASONER:
            steps.append(
                {
                    "name": "REASONING_SUPPORT",
                    "module": self.MODULE_REASONER,
                    "description": (
                        "Ocenić strategie i ryzyko."
                    ),
                    "priority": priority,
                }
            )

        if isinstance(decomposition, dict):
            for subgoal in decomposition.get("subgoals", []):
                if not isinstance(subgoal, dict):
                    continue

                steps.append(
                    {
                        "name": (
                            "PHASE_"
                            + str(
                                subgoal.get(
                                    "subgoal_type",
                                    "UNKNOWN",
                                )
                            ).strip().upper()
                        ),
                        "module": selected_module,
                        "description": str(
                            subgoal.get(
                                "description",
                                subgoal.get("title", ""),
                            )
                        ).strip(),
                        "priority": str(
                            subgoal.get(
                                "priority",
                                priority,
                            )
                        ).strip().upper(),
                        "proposal_id": str(
                            subgoal.get("proposal_id", "")
                        ),
                        "dependencies": list(
                            subgoal.get("dependencies", [])
                        ),
                        "success_criteria": list(
                            subgoal.get("success_criteria", [])
                        ),
                    }
                )

        steps.append(
            {
                "name": "EXECUTE_SELECTED_MODULE",
                "module": selected_module,
                "description": (
                    "Uruchomić wybrany moduł."
                ),
                "priority": priority,
            }
        )

        steps.append(
            {
                "name": "VALIDATE_RESULT",
                "module": "PROJECT_DIRECTOR",
                "description": (
                    "Zweryfikować wynik i zapisać wnioski."
                ),
                "priority": priority,
            }
        )

        return steps

    def _estimate_complexity(
        self,
        lowered: str,
    ) -> str:

        high_signals = (
            "cały projekt",
            "caly projekt",
            "architektura",
            "autonomicznie",
            "wiele modułów",
            "wiele modulow",
            "długoterminowy",
            "dlugoterminowy",
            "pełna integracja",
            "pelna integracja",
        )

        low_signals = (
            "summary",
            "status",
            "lista",
            "pokaż",
            "pokaz",
        )

        if self._contains_any(
            lowered,
            high_signals,
        ):
            return "HIGH"

        if self._contains_any(
            lowered,
            low_signals,
        ):
            return "LOW"

        return "MEDIUM"

    def _estimate_urgency(
        self,
        lowered: str,
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
            lowered,
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
            lowered,
            (
                "pilne",
                "urgent",
                "ważne",
                "wazne",
            ),
        ):
            return "HIGH"

        return "MEDIUM"

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
