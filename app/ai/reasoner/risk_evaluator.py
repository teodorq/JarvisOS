"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class RiskLevel(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskCategory(str, Enum):
    SCOPE = "SCOPE"
    COMPLEXITY = "COMPLEXITY"
    DEPENDENCIES = "DEPENDENCIES"
    IMPORTS = "IMPORTS"
    FILE_CHANGES = "FILE_CHANGES"
    REGRESSION = "REGRESSION"
    ARCHITECTURE = "ARCHITECTURE"
    DATA_LOSS = "DATA_LOSS"
    SECURITY = "SECURITY"
    VALIDATION = "VALIDATION"
    ROLLBACK = "ROLLBACK"
    RESEARCH = "RESEARCH"
    CONFIDENCE = "CONFIDENCE"
    EXECUTION = "EXECUTION"


class RiskDecision(str, Enum):
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_CAUTION = "ACCEPT_WITH_CAUTION"
    REQUIRE_RESEARCH = "REQUIRE_RESEARCH"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECT = "REJECT"


@dataclass
class RiskFactor:
    factor_id: str
    category: str
    name: str
    description: str
    score: float
    weight: float
    weighted_score: float
    severity: str
    evidence: list[str] = field(default_factory=list)
    mitigation: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptionRiskAssessment:
    assessment_id: str
    option_id: str
    option_name: str
    strategy_type: str
    total_score: float
    normalized_score: float
    risk_level: str
    decision: str
    confidence: float
    requires_confirmation: bool
    requires_research: bool
    requires_manual_review: bool
    recommended: bool
    risk_factors: list[dict[str, Any]]
    strengths: list[str]
    weaknesses: list[str]
    mitigation_plan: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskEvaluationResult:
    evaluation_id: str
    goal: dict[str, Any]
    assessments: list[dict[str, Any]]
    safest_option_id: str | None
    recommended_option_id: str | None
    rejected_option_ids: list[str]
    overall_risk_level: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskEvaluator:

    CATEGORY_WEIGHTS = {
        RiskCategory.SCOPE: 1.0,
        RiskCategory.COMPLEXITY: 1.1,
        RiskCategory.DEPENDENCIES: 1.2,
        RiskCategory.IMPORTS: 1.0,
        RiskCategory.FILE_CHANGES: 1.0,
        RiskCategory.REGRESSION: 1.4,
        RiskCategory.ARCHITECTURE: 1.3,
        RiskCategory.DATA_LOSS: 1.5,
        RiskCategory.SECURITY: 1.6,
        RiskCategory.VALIDATION: 1.2,
        RiskCategory.ROLLBACK: 1.1,
        RiskCategory.RESEARCH: 0.9,
        RiskCategory.CONFIDENCE: 1.0,
        RiskCategory.EXECUTION: 1.2,
    }

    SCOPE_SCORES = {
        "NONE": 0.0,
        "SINGLE_FILE": 1.0,
        "MODULE": 2.5,
        "MULTI_MODULE": 4.0,
        "PROJECT": 5.0,
    }

    EFFORT_SCORES = {
        "LOW": 1.0,
        "MEDIUM": 2.5,
        "HIGH": 4.0,
    }

    COMPLEXITY_SCORES = {
        "LOW": 1.0,
        "MEDIUM": 2.5,
        "HIGH": 4.5,
    }

    STRATEGY_BASE_RISK = {
        "DIRECT_RESPONSE": 0.3,
        "ANALYSIS_ONLY": 0.5,
        "RESEARCH_FIRST": 0.8,
        "MANUAL_REVIEW": 0.2,
        "MINIMAL_CHANGE": 1.3,
        "SAFE_FIX": 2.0,
        "TARGETED_REFACTOR": 3.0,
        "FEATURE_EXTENSION": 3.2,
        "FULL_REFACTOR": 4.7,
    }

    CRITICAL_RISK_PHRASES = {
        "utrata danych",
        "format dysku",
        "usuń cały projekt",
        "delete database",
        "drop database",
        "baza produkcyjna",
        "production database",
        "wyłącz zabezpieczenia",
        "disable security",
        "usuń backup",
    }

    DATA_RISK_PHRASES = {
        "delete",
        "usuń",
        "kasuj",
        "remove",
        "drop",
        "truncate",
        "overwrite",
        "nadpisz",
        "database",
        "baza danych",
    }

    SECURITY_RISK_PHRASES = {
        "password",
        "hasło",
        "token",
        "secret",
        "credential",
        "credentials",
        "api key",
        "klucz api",
        "security",
        "bezpieczeństwo",
        "firewall",
        "antywirus",
        "administrator",
        "admin",
        "uprawnienia",
        "remote",
        "zdalny",
        "network",
        "sieć",
    }

    def evaluate(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_goal = self._normalize_goal(goal)
        options = self._extract_options(options_result)
        normalized_research = self._normalize_context(
            research_context
        )
        normalized_project = self._normalize_context(
            project_context
        )

        assessments: list[OptionRiskAssessment] = []

        for option in options:
            assessment = self._evaluate_option(
                goal=normalized_goal,
                option=option,
                research_context=normalized_research,
                project_context=normalized_project,
            )
            assessments.append(assessment)

        safest_option_id = self._select_safest_option(
            assessments
        )

        recommended_option_id = self._select_recommended_option(
            assessments
        )

        for assessment in assessments:
            assessment.recommended = (
                assessment.option_id
                == recommended_option_id
            )

        rejected_option_ids = [
            assessment.option_id
            for assessment in assessments
            if assessment.decision
            == RiskDecision.REJECT.value
        ]

        result = RiskEvaluationResult(
            evaluation_id=f"risk_evaluation_{uuid4().hex}",
            goal=normalized_goal,
            assessments=[
                assessment.to_dict()
                for assessment in assessments
            ],
            safest_option_id=safest_option_id,
            recommended_option_id=recommended_option_id,
            rejected_option_ids=rejected_option_ids,
            overall_risk_level=self._calculate_overall_risk(
                assessments
            ),
            metadata={
                "evaluator_version": "1.0.0",
                "assessments_count": len(assessments),
                "research_available": bool(
                    normalized_research
                ),
                "project_context_available": bool(
                    normalized_project
                ),
            },
        )

        return result.to_dict()

    def assess(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.evaluate(
            goal=goal,
            options_result=options_result,
            research_context=research_context,
            project_context=project_context,
        )

    def analyze(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.evaluate(
            goal=goal,
            options_result=options_result,
            research_context=research_context,
            project_context=project_context,
        )

    def _evaluate_option(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
        research_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> OptionRiskAssessment:

        normalized_option = self._normalize_option(option)

        factors = [
            self._evaluate_scope_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_complexity_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_dependency_risk(
                normalized_option,
                project_context,
            ),
            self._evaluate_import_risk(
                normalized_option,
                project_context,
            ),
            self._evaluate_file_change_risk(
                normalized_option,
                project_context,
            ),
            self._evaluate_regression_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_architecture_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_data_loss_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_security_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_validation_risk(
                normalized_option,
                project_context,
            ),
            self._evaluate_rollback_risk(
                normalized_option,
                project_context,
            ),
            self._evaluate_research_risk(
                goal,
                normalized_option,
                research_context,
            ),
            self._evaluate_confidence_risk(
                goal,
                normalized_option,
            ),
            self._evaluate_execution_risk(
                normalized_option,
            ),
        ]

        total_score = sum(
            factor.weighted_score
            for factor in factors
        )

        max_score = sum(
            5.0 * factor.weight
            for factor in factors
        )

        normalized_score = 0.0

        if max_score > 0:
            normalized_score = (
                total_score / max_score
            ) * 100.0

        normalized_score = round(
            max(
                0.0,
                min(
                    100.0,
                    normalized_score,
                ),
            ),
            2,
        )

        risk_level = self._risk_level_from_score(
            normalized_score
        )

        confidence = self._calculate_assessment_confidence(
            goal=goal,
            option=normalized_option,
            research_context=research_context,
            project_context=project_context,
        )

        requires_manual_review = (
            self._requires_manual_review(
                risk_level=risk_level,
                score=normalized_score,
                factors=factors,
            )
        )

        requires_confirmation = (
            self._requires_confirmation(
                goal=goal,
                option=normalized_option,
                risk_level=risk_level,
            )
        )

        requires_research = self._requires_research(
            goal=goal,
            option=normalized_option,
            risk_level=risk_level,
            research_context=research_context,
        )

        decision = self._make_risk_decision(
            risk_level=risk_level,
            score=normalized_score,
            requires_manual_review=requires_manual_review,
            requires_confirmation=requires_confirmation,
            requires_research=requires_research,
            factors=factors,
        )

        return OptionRiskAssessment(
            assessment_id=f"assessment_{uuid4().hex}",
            option_id=normalized_option["option_id"],
            option_name=normalized_option["name"],
            strategy_type=normalized_option[
                "strategy_type"
            ],
            total_score=round(total_score, 2),
            normalized_score=normalized_score,
            risk_level=risk_level.value,
            decision=decision.value,
            confidence=confidence,
            requires_confirmation=requires_confirmation,
            requires_research=requires_research,
            requires_manual_review=requires_manual_review,
            recommended=False,
            risk_factors=[
                factor.to_dict()
                for factor in factors
            ],
            strengths=self._collect_strengths(
                normalized_option,
                factors,
            ),
            weaknesses=self._collect_weaknesses(
                normalized_option,
                factors,
            ),
            mitigation_plan=self._build_mitigation_plan(
                option=normalized_option,
                factors=factors,
                requires_research=requires_research,
                requires_confirmation=requires_confirmation,
                requires_manual_review=requires_manual_review,
            ),
            metadata={
                "scope": normalized_option["scope"],
                "effort": normalized_option["effort"],
                "estimated_steps": normalized_option[
                    "estimated_steps"
                ],
                "score_hint": normalized_option[
                    "score_hint"
                ],
            },
        )

    def _evaluate_scope_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        score = self.SCOPE_SCORES.get(
            option["scope"],
            2.5,
        )

        evidence = [
            f"Zakres strategii: {option['scope']}."
        ]

        if len(goal["detected_modules"]) >= 2:
            score += 0.7
            evidence.append(
                "Cel obejmuje wiele modułów."
            )

        return self._make_factor(
            category=RiskCategory.SCOPE,
            name="Ryzyko zakresu",
            description=(
                "Ryzyko wynikające z wielkości "
                "obszaru objętego zmianami."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Ograniczyć zakres do niezbędnego minimum.",
                "Podzielić zmianę na mniejsze transakcje.",
            ],
        )

    def _evaluate_complexity_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        goal_score = self.COMPLEXITY_SCORES.get(
            goal["complexity"],
            2.5,
        )

        effort_score = self.EFFORT_SCORES.get(
            option["effort"],
            2.5,
        )

        score = (
            goal_score + effort_score
        ) / 2.0

        if option["estimated_steps"] >= 10:
            score += 0.7

        return self._make_factor(
            category=RiskCategory.COMPLEXITY,
            name="Ryzyko złożoności",
            description=(
                "Ryzyko wynikające z trudności celu "
                "i liczby kroków wykonania."
            ),
            score=score,
            evidence=[
                f"Złożoność celu: {goal['complexity']}.",
                f"Wysiłek strategii: {option['effort']}.",
                (
                    "Liczba kroków: "
                    f"{option['estimated_steps']}."
                ),
            ],
            mitigation=[
                "Podzielić wykonanie na etapy.",
                "Walidować wynik po każdym etapie.",
            ],
        )

    def _evaluate_dependency_risk(
        self,
        option: dict[str, Any],
        project_context: dict[str, Any],
    ) -> RiskFactor:

        score = self.SCOPE_SCORES.get(
            option["scope"],
            2.5,
        )

        dependency_count = self._extract_number(
            project_context,
            [
                "dependency_count",
                "dependencies_count",
                "affected_dependencies",
            ],
        )

        evidence = [
            f"Zakres strategii: {option['scope']}."
        ]

        if dependency_count is not None:
            evidence.append(
                f"Liczba zależności: {dependency_count}."
            )

            if dependency_count >= 20:
                score += 1.5
            elif dependency_count >= 10:
                score += 1.0
            elif dependency_count >= 5:
                score += 0.5

        return self._make_factor(
            category=RiskCategory.DEPENDENCIES,
            name="Ryzyko zależności",
            description=(
                "Ryzyko wpływu zmian na moduły "
                "i elementy zależne."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Uruchomić Dependency Graph.",
                "Sprawdzić Reference Finder.",
                "Zweryfikować moduły zależne.",
            ],
        )

    def _evaluate_import_risk(
        self,
        option: dict[str, Any],
        project_context: dict[str, Any],
    ) -> RiskFactor:

        score_map = {
            "DIRECT_RESPONSE": 0.0,
            "ANALYSIS_ONLY": 0.0,
            "RESEARCH_FIRST": 0.3,
            "MANUAL_REVIEW": 0.2,
            "MINIMAL_CHANGE": 1.0,
            "SAFE_FIX": 2.0,
            "TARGETED_REFACTOR": 3.0,
            "FEATURE_EXTENSION": 3.2,
            "FULL_REFACTOR": 4.5,
        }

        score = score_map.get(
            option["strategy_type"],
            2.0,
        )

        affected_imports = self._extract_number(
            project_context,
            [
                "affected_imports",
                "imports_count",
                "changed_imports",
            ],
        )

        evidence = [
            (
                "Typ strategii: "
                f"{option['strategy_type']}."
            )
        ]

        if affected_imports is not None:
            evidence.append(
                f"Importy objęte zmianą: {affected_imports}."
            )

            if affected_imports >= 15:
                score += 1.2
            elif affected_imports >= 8:
                score += 0.8
            elif affected_imports >= 3:
                score += 0.4

        return self._make_factor(
            category=RiskCategory.IMPORTS,
            name="Ryzyko importów",
            description=(
                "Ryzyko uszkodzenia importów "
                "lub utworzenia zależności cyklicznych."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Uruchomić Import Analyzer.",
                "Sprawdzić importy cykliczne.",
                "Wykonać walidację importów.",
            ],
        )

    def _evaluate_file_change_risk(
        self,
        option: dict[str, Any],
        project_context: dict[str, Any],
    ) -> RiskFactor:

        score = self.SCOPE_SCORES.get(
            option["scope"],
            2.5,
        )

        affected_files = self._extract_number(
            project_context,
            [
                "affected_files",
                "files_count",
                "changed_files",
            ],
        )

        evidence = [
            f"Zakres strategii: {option['scope']}."
        ]

        if affected_files is not None:
            evidence.append(
                f"Liczba plików: {affected_files}."
            )

            if affected_files >= 20:
                score += 1.5
            elif affected_files >= 10:
                score += 1.0
            elif affected_files >= 5:
                score += 0.5

        return self._make_factor(
            category=RiskCategory.FILE_CHANGES,
            name="Ryzyko zmian plików",
            description=(
                "Ryzyko wynikające z liczby "
                "modyfikowanych plików."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Utworzyć backup przed zmianą.",
                "Ograniczyć liczbę plików w patchu.",
                "Pokazać pełny Patch Preview.",
            ],
        )

    def _evaluate_regression_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        score_map = {
            "DIRECT_RESPONSE": 0.0,
            "ANALYSIS_ONLY": 0.0,
            "RESEARCH_FIRST": 0.3,
            "MANUAL_REVIEW": 0.2,
            "MINIMAL_CHANGE": 1.2,
            "SAFE_FIX": 2.0,
            "TARGETED_REFACTOR": 3.4,
            "FEATURE_EXTENSION": 3.6,
            "FULL_REFACTOR": 4.8,
        }

        score = score_map.get(
            option["strategy_type"],
            2.5,
        )

        if goal["complexity"] == "HIGH":
            score += 0.6

        if option["scope"] in {
            "MULTI_MODULE",
            "PROJECT",
        }:
            score += 0.6

        return self._make_factor(
            category=RiskCategory.REGRESSION,
            name="Ryzyko regresji",
            description=(
                "Ryzyko uszkodzenia wcześniej "
                "działających funkcji."
            ),
            score=score,
            evidence=[
                (
                    "Typ strategii: "
                    f"{option['strategy_type']}."
                ),
                (
                    "Złożoność celu: "
                    f"{goal['complexity']}."
                ),
                f"Zakres: {option['scope']}.",
            ],
            mitigation=[
                "Uruchomić dostępne testy.",
                "Wykonać walidację składni i importów.",
                "Zachować natychmiastowy rollback.",
            ],
        )

    def _evaluate_architecture_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        score_map = {
            "DIRECT_RESPONSE": 0.0,
            "ANALYSIS_ONLY": 0.0,
            "RESEARCH_FIRST": 0.5,
            "MANUAL_REVIEW": 0.2,
            "MINIMAL_CHANGE": 0.8,
            "SAFE_FIX": 1.6,
            "TARGETED_REFACTOR": 3.4,
            "FEATURE_EXTENSION": 3.1,
            "FULL_REFACTOR": 5.0,
        }

        score = score_map.get(
            option["strategy_type"],
            2.0,
        )

        if goal["goal_type"] == "REFACTOR":
            score += 0.4

        return self._make_factor(
            category=RiskCategory.ARCHITECTURE,
            name="Ryzyko architektoniczne",
            description=(
                "Ryzyko wpływu zmian na strukturę "
                "i kontrakty projektu."
            ),
            score=score,
            evidence=[
                (
                    "Typ strategii: "
                    f"{option['strategy_type']}."
                ),
                f"Typ celu: {goal['goal_type']}.",
            ],
            mitigation=[
                "Zachować publiczne interfejsy.",
                "Uruchomić Change Impact Analyzer.",
                "Wdrażać zmiany etapami.",
            ],
        )

    def _evaluate_data_loss_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        text = self._combined_text(
            goal,
            option,
        )

        critical_matches = self._find_matches(
            text,
            self.CRITICAL_RISK_PHRASES,
        )

        data_matches = self._find_matches(
            text,
            self.DATA_RISK_PHRASES,
        )

        score = 0.2
        evidence: list[str] = []

        if critical_matches:
            score = 5.0
            evidence.append(
                "Wykryto krytyczne operacje: "
                f"{critical_matches}."
            )
        elif data_matches:
            score = 3.8
            evidence.append(
                "Wykryto operacje na danych: "
                f"{data_matches}."
            )
        else:
            evidence.append(
                "Nie wykryto operacji grożących "
                "utratą danych."
            )

        return self._make_factor(
            category=RiskCategory.DATA_LOSS,
            name="Ryzyko utraty danych",
            description=(
                "Ryzyko usunięcia, nadpisania "
                "lub uszkodzenia danych."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Wykonać pełny backup.",
                "Nie usuwać danych bez akceptacji.",
                "Zweryfikować możliwość rollbacku.",
            ],
        )

    def _evaluate_security_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        text = self._combined_text(
            goal,
            option,
        )

        matches = self._find_matches(
            text,
            self.SECURITY_RISK_PHRASES,
        )

        score = 0.4
        evidence: list[str] = []

        if matches:
            score = 4.0
            evidence.append(
                "Wykryto obszary bezpieczeństwa: "
                f"{matches}."
            )
        else:
            evidence.append(
                "Brak bezpośrednich zmian "
                "dotyczących bezpieczeństwa."
            )

        if (
            matches
            and option["scope"]
            in {"MULTI_MODULE", "PROJECT"}
        ):
            score += 0.8

        return self._make_factor(
            category=RiskCategory.SECURITY,
            name="Ryzyko bezpieczeństwa",
            description=(
                "Ryzyko wpływu zmian na sekrety, "
                "uprawnienia i zabezpieczenia."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Nie zapisywać sekretów w kodzie.",
                "Zweryfikować uprawnienia.",
                "Wymagać ręcznej akceptacji.",
                "Przeprowadzić walidację bezpieczeństwa.",
            ],
        )

    def _evaluate_validation_risk(
        self,
        option: dict[str, Any],
        project_context: dict[str, Any],
    ) -> RiskFactor:

        plan_text = " ".join(
            option["execution_plan"]
        ).lower()

        has_validation = any(
            phrase in plan_text
            for phrase in [
                "walidac",
                "test",
                "składni",
                "import",
                "validation",
                "verify",
            ]
        )

        tests_available = self._extract_bool(
            project_context,
            [
                "tests_available",
                "has_tests",
                "validation_available",
            ],
        )

        score = 1.0 if has_validation else 4.0

        evidence = [
            (
                "Plan zawiera walidację."
                if has_validation
                else "Plan nie zawiera walidacji."
            )
        ]

        if tests_available is True:
            score -= 0.5
            evidence.append(
                "Projekt posiada testy lub walidatory."
            )

        if tests_available is False:
            score += 0.7
            evidence.append(
                "Projekt nie posiada potwierdzonych testów."
            )

        return self._make_factor(
            category=RiskCategory.VALIDATION,
            name="Ryzyko walidacji",
            description=(
                "Ryzyko niewystarczającego "
                "sprawdzenia wykonanych zmian."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Uruchomić DeveloperValidator.",
                "Sprawdzić składnię.",
                "Sprawdzić importy.",
                "Uruchomić testy projektu.",
            ],
        )

    def _evaluate_rollback_risk(
        self,
        option: dict[str, Any],
        project_context: dict[str, Any],
    ) -> RiskFactor:

        plan_text = " ".join(
            option["execution_plan"]
        ).lower()

        has_backup = any(
            phrase in plan_text
            for phrase in [
                "backup",
                "rollback",
                "kopia",
                "przywró",
            ]
        )

        rollback_available = self._extract_bool(
            project_context,
            [
                "rollback_available",
                "has_rollback",
                "backup_available",
            ],
        )

        score = 1.0 if has_backup else 3.5

        evidence = [
            (
                "Plan zawiera backup lub rollback."
                if has_backup
                else "Plan nie zawiera backupu ani rollbacku."
            )
        ]

        if rollback_available is True:
            score -= 0.7
            evidence.append(
                "Mechanizm rollbacku jest dostępny."
            )

        if rollback_available is False:
            score += 1.0
            evidence.append(
                "Brak potwierdzonego rollbacku."
            )

        if option["scope"] in {
            "MULTI_MODULE",
            "PROJECT",
        }:
            score += 0.5

        return self._make_factor(
            category=RiskCategory.ROLLBACK,
            name="Ryzyko rollbacku",
            description=(
                "Ryzyko braku możliwości "
                "bezpiecznego cofnięcia zmian."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Utworzyć Backup Bundle.",
                "Sprawdzić Rollback Manager.",
                "Nie wykonywać szerokich zmian bez backupu.",
            ],
        )

    def _evaluate_research_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
        research_context: dict[str, Any],
    ) -> RiskFactor:

        needs_research = (
            goal["requires_research"]
            or option["requires_research"]
        )

        has_research = bool(research_context)

        if needs_research and not has_research:
            score = 4.0
            evidence = [
                "Strategia wymaga researchu, "
                "ale ResearchContext jest pusty."
            ]
        elif needs_research and has_research:
            score = 1.0
            evidence = [
                "ResearchContext jest dostępny."
            ]
        else:
            score = 0.5
            evidence = [
                "Strategia nie wymaga dodatkowego researchu."
            ]

        return self._make_factor(
            category=RiskCategory.RESEARCH,
            name="Ryzyko braku researchu",
            description=(
                "Ryzyko działania bez wystarczającej "
                "analizy projektu."
            ),
            score=score,
            evidence=evidence,
            mitigation=[
                "Uruchomić ResearchWorkflow.",
                "Sprawdzić kompletność wyników researchu.",
            ],
        )

    def _evaluate_confidence_risk(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> RiskFactor:

        combined_confidence = (
            goal["confidence"]
            + option["score_hint"]
        ) / 2.0

        score = (
            1.0 - combined_confidence
        ) * 5.0

        return self._make_factor(
            category=RiskCategory.CONFIDENCE,
            name="Ryzyko niskiej pewności",
            description=(
                "Ryzyko wynikające z niskiej "
                "pewności klasyfikacji i strategii."
            ),
            score=score,
            evidence=[
                (
                    "Pewność celu: "
                    f"{round(goal['confidence'], 2)}."
                ),
                (
                    "Ocena opcji: "
                    f"{round(option['score_hint'], 2)}."
                ),
            ],
            mitigation=[
                "Uruchomić dodatkową analizę.",
                "Wymagać ręcznego przeglądu przy niskiej pewności.",
            ],
        )

    def _evaluate_execution_risk(
        self,
        option: dict[str, Any],
    ) -> RiskFactor:

        score = self.STRATEGY_BASE_RISK.get(
            option["strategy_type"],
            2.5,
        )

        if option["requires_developer"]:
            score += 0.4

        if option["estimated_steps"] >= 10:
            score += 0.5

        return self._make_factor(
            category=RiskCategory.EXECUTION,
            name="Ryzyko wykonania",
            description=(
                "Ryzyko związane z wykonaniem "
                "wybranej strategii."
            ),
            score=score,
            evidence=[
                (
                    "Typ strategii: "
                    f"{option['strategy_type']}."
                ),
                (
                    "Wymaga DeveloperController: "
                    f"{option['requires_developer']}."
                ),
                (
                    "Liczba kroków: "
                    f"{option['estimated_steps']}."
                ),
            ],
            mitigation=[
                "Użyć DeveloperController.",
                "Pokazać Patch Preview.",
                "Przerwać proces po błędzie walidacji.",
            ],
        )

    def _make_factor(
        self,
        category: RiskCategory,
        name: str,
        description: str,
        score: float,
        evidence: list[str],
        mitigation: list[str],
    ) -> RiskFactor:

        normalized_score = self._clamp_score(
            score
        )

        weight = self.CATEGORY_WEIGHTS[
            category
        ]

        return RiskFactor(
            factor_id=f"risk_factor_{uuid4().hex}",
            category=category.value,
            name=name,
            description=description,
            score=round(normalized_score, 2),
            weight=round(weight, 2),
            weighted_score=round(
                normalized_score * weight,
                2,
            ),
            severity=self._severity_from_factor_score(
                normalized_score
            ),
            evidence=evidence,
            mitigation=mitigation,
            metadata={
                "evaluator_version": "1.0.0",
            },
        )

    def _make_risk_decision(
        self,
        risk_level: RiskLevel,
        score: float,
        requires_manual_review: bool,
        requires_confirmation: bool,
        requires_research: bool,
        factors: list[RiskFactor],
    ) -> RiskDecision:

        critical_factor = any(
            factor.severity
            == RiskLevel.CRITICAL.value
            for factor in factors
        )

        if (
            risk_level == RiskLevel.CRITICAL
            or score >= 85.0
            or critical_factor
        ):
            return RiskDecision.REJECT

        if requires_manual_review:
            return RiskDecision.MANUAL_REVIEW

        if requires_research:
            return RiskDecision.REQUIRE_RESEARCH

        if requires_confirmation:
            return RiskDecision.REQUIRE_CONFIRMATION

        if risk_level in {
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
        }:
            return RiskDecision.ACCEPT_WITH_CAUTION

        return RiskDecision.ACCEPT

    def _requires_manual_review(
        self,
        risk_level: RiskLevel,
        score: float,
        factors: list[RiskFactor],
    ) -> bool:

        if risk_level == RiskLevel.HIGH:
            return True

        if score >= 65.0:
            return True

        sensitive_categories = {
            RiskCategory.DATA_LOSS.value,
            RiskCategory.SECURITY.value,
        }

        for factor in factors:
            if (
                factor.category in sensitive_categories
                and factor.score >= 3.5
            ):
                return True

        return False

    def _requires_confirmation(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
        risk_level: RiskLevel,
    ) -> bool:

        if option["requires_confirmation"]:
            return True

        if goal["requires_confirmation"]:
            return True

        if option["requires_developer"]:
            return True

        if risk_level in {
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }:
            return True

        return False

    def _requires_research(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
        risk_level: RiskLevel,
        research_context: dict[str, Any],
    ) -> bool:

        requested = (
            goal["requires_research"]
            or option["requires_research"]
        )

        if requested and not research_context:
            return True

        if (
            risk_level in {
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            }
            and not research_context
        ):
            return True

        return False

    def _calculate_assessment_confidence(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
        research_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> float:

        confidence = (
            goal["confidence"]
            + option["score_hint"]
        ) / 2.0

        if research_context:
            confidence += 0.08

        if project_context:
            confidence += 0.06

        if option["execution_plan"]:
            confidence += 0.04

        return round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            2,
        )

    def _collect_strengths(
        self,
        option: dict[str, Any],
        factors: list[RiskFactor],
    ) -> list[str]:

        strengths = list(
            option["expected_benefits"]
        )

        low_risk_categories = [
            factor.category
            for factor in factors
            if factor.score <= 1.5
        ]

        if low_risk_categories:
            strengths.append(
                "Niskie ryzyko w obszarach: "
                + ", ".join(low_risk_categories[:5])
                + "."
            )

        if option["scope"] in {
            "NONE",
            "SINGLE_FILE",
        }:
            strengths.append(
                "Ograniczony zakres zmian."
            )

        if option["strategy_type"] in {
            "MINIMAL_CHANGE",
            "SAFE_FIX",
            "RESEARCH_FIRST",
            "MANUAL_REVIEW",
        }:
            strengths.append(
                "Strategia preferuje bezpieczne wykonanie."
            )

        return self._unique_strings(
            strengths
        )

    def _collect_weaknesses(
        self,
        option: dict[str, Any],
        factors: list[RiskFactor],
    ) -> list[str]:

        weaknesses = list(
            option["expected_drawbacks"]
        )

        high_factors = [
            factor
            for factor in factors
            if factor.score >= 3.5
        ]

        for factor in high_factors:
            weaknesses.append(
                f"{factor.name}: {factor.severity}."
            )

        if option["estimated_steps"] >= 10:
            weaknesses.append(
                "Strategia wymaga wielu kroków wykonania."
            )

        return self._unique_strings(
            weaknesses
        )

    def _build_mitigation_plan(
        self,
        option: dict[str, Any],
        factors: list[RiskFactor],
        requires_research: bool,
        requires_confirmation: bool,
        requires_manual_review: bool,
    ) -> list[str]:

        plan: list[str] = []

        sorted_factors = sorted(
            factors,
            key=lambda factor: factor.weighted_score,
            reverse=True,
        )

        for factor in sorted_factors:
            if factor.score < 2.3:
                continue

            plan.extend(
                factor.mitigation
            )

        if requires_research:
            plan.insert(
                0,
                "Uruchomić ResearchWorkflow przed wykonaniem zmian.",
            )

        if requires_confirmation:
            plan.append(
                "Pokazać użytkownikowi strategię i Patch Preview.",
            )

        if requires_manual_review:
            plan.append(
                "Zatrzymać automatyczne wykonanie do ręcznej decyzji.",
            )

        if option["requires_developer"]:
            plan.append(
                "Wykonać zmiany wyłącznie przez DeveloperController.",
            )

        return self._unique_strings(
            plan
        )

    def _select_safest_option(
        self,
        assessments: list[OptionRiskAssessment],
    ) -> str | None:

        if not assessments:
            return None

        safest = min(
            assessments,
            key=lambda assessment: (
                assessment.normalized_score,
                -assessment.confidence,
            ),
        )

        return safest.option_id

    def _select_recommended_option(
        self,
        assessments: list[OptionRiskAssessment],
    ) -> str | None:

        if not assessments:
            return None

        usable = [
            assessment
            for assessment in assessments
            if assessment.decision
            != RiskDecision.REJECT.value
        ]

        if not usable:
            return None

        decision_penalties = {
            RiskDecision.ACCEPT.value: 0.0,
            RiskDecision.ACCEPT_WITH_CAUTION.value: 5.0,
            RiskDecision.REQUIRE_CONFIRMATION.value: 7.0,
            RiskDecision.REQUIRE_RESEARCH.value: 9.0,
            RiskDecision.MANUAL_REVIEW.value: 14.0,
            RiskDecision.REJECT.value: 100.0,
        }

        def recommendation_score(
            assessment: OptionRiskAssessment,
        ) -> float:

            confidence_bonus = (
                assessment.confidence * 30.0
            )

            risk_penalty = (
                assessment.normalized_score
            )

            decision_penalty = decision_penalties.get(
                assessment.decision,
                10.0,
            )

            return (
                confidence_bonus
                - risk_penalty
                - decision_penalty
            )

        recommended = max(
            usable,
            key=recommendation_score,
        )

        return recommended.option_id

    def _calculate_overall_risk(
        self,
        assessments: list[OptionRiskAssessment],
    ) -> str:

        if not assessments:
            return RiskLevel.VERY_LOW.value

        recommended = next(
            (
                assessment
                for assessment in assessments
                if assessment.recommended
            ),
            None,
        )

        if recommended is not None:
            return recommended.risk_level

        safest = min(
            assessments,
            key=lambda assessment: (
                assessment.normalized_score
            ),
        )

        return safest.risk_level

    def _severity_from_factor_score(
        self,
        score: float,
    ) -> str:

        if score >= 4.5:
            return RiskLevel.CRITICAL.value

        if score >= 3.5:
            return RiskLevel.HIGH.value

        if score >= 2.3:
            return RiskLevel.MEDIUM.value

        if score >= 1.0:
            return RiskLevel.LOW.value

        return RiskLevel.VERY_LOW.value

    def _risk_level_from_score(
        self,
        score: float,
    ) -> RiskLevel:

        if score >= 80.0:
            return RiskLevel.CRITICAL

        if score >= 60.0:
            return RiskLevel.HIGH

        if score >= 35.0:
            return RiskLevel.MEDIUM

        if score >= 15.0:
            return RiskLevel.LOW

        return RiskLevel.VERY_LOW

    def _extract_options(
        self,
        options_result: dict[str, Any] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if isinstance(options_result, list):
            return [
                option
                for option in options_result
                if isinstance(option, dict)
            ]

        if isinstance(options_result, dict):
            options = options_result.get(
                "options",
                [],
            )

            if isinstance(options, list):
                return [
                    option
                    for option in options
                    if isinstance(option, dict)
                ]

        raise TypeError(
            "RiskEvaluator wymaga listy opcji "
            "lub wyniku OptionGenerator."
        )

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(goal, dict):
            raise TypeError(
                "RiskEvaluator wymaga celu typu dict."
            )

        confidence = self._safe_float(
            goal.get(
                "confidence",
                0.0,
            ),
            0.0,
        )

        return {
            "original_request": str(
                goal.get(
                    "original_request",
                    "",
                )
            ),
            "goal": str(
                goal.get(
                    "goal",
                    "",
                )
            ),
            "goal_type": str(
                goal.get(
                    "goal_type",
                    "UNKNOWN",
                )
            ).upper(),
            "priority": str(
                goal.get(
                    "priority",
                    "LOW",
                )
            ).upper(),
            "complexity": str(
                goal.get(
                    "complexity",
                    "LOW",
                )
            ).upper(),
            "requires_research": bool(
                goal.get(
                    "requires_research",
                    False,
                )
            ),
            "requires_developer": bool(
                goal.get(
                    "requires_developer",
                    False,
                )
            ),
            "requires_confirmation": bool(
                goal.get(
                    "requires_confirmation",
                    False,
                )
            ),
            "confidence": max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            "keywords": self._safe_list(
                goal.get(
                    "keywords",
                    [],
                )
            ),
            "detected_modules": self._safe_list(
                goal.get(
                    "detected_modules",
                    [],
                )
            ),
            "metadata": self._safe_dict(
                goal.get(
                    "metadata",
                    {},
                )
            ),
        }

    def _normalize_option(
        self,
        option: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(option, dict):
            raise TypeError(
                "Opcja musi być typu dict."
            )

        score_hint = self._safe_float(
            option.get(
                "score_hint",
                0.5,
            ),
            0.5,
        )

        estimated_steps = self._safe_int(
            option.get(
                "estimated_steps",
                1,
            ),
            1,
        )

        option_id = str(
            option.get(
                "option_id",
                "",
            )
        ).strip()

        if not option_id:
            option_id = f"option_{uuid4().hex}"

        return {
            "option_id": option_id,
            "name": str(
                option.get(
                    "name",
                    "Nieznana opcja",
                )
            ),
            "description": str(
                option.get(
                    "description",
                    "",
                )
            ),
            "strategy_type": str(
                option.get(
                    "strategy_type",
                    "MANUAL_REVIEW",
                )
            ).upper(),
            "scope": str(
                option.get(
                    "scope",
                    "NONE",
                )
            ).upper(),
            "effort": str(
                option.get(
                    "effort",
                    "LOW",
                )
            ).upper(),
            "requires_research": bool(
                option.get(
                    "requires_research",
                    False,
                )
            ),
            "requires_developer": bool(
                option.get(
                    "requires_developer",
                    False,
                )
            ),
            "requires_confirmation": bool(
                option.get(
                    "requires_confirmation",
                    False,
                )
            ),
            "estimated_steps": max(
                0,
                estimated_steps,
            ),
            "expected_benefits": self._safe_list(
                option.get(
                    "expected_benefits",
                    [],
                )
            ),
            "expected_drawbacks": self._safe_list(
                option.get(
                    "expected_drawbacks",
                    [],
                )
            ),
            "assumptions": self._safe_list(
                option.get(
                    "assumptions",
                    [],
                )
            ),
            "execution_plan": self._safe_list(
                option.get(
                    "execution_plan",
                    [],
                )
            ),
            "score_hint": max(
                0.0,
                min(
                    1.0,
                    score_hint,
                ),
            ),
            "metadata": self._safe_dict(
                option.get(
                    "metadata",
                    {},
                )
            ),
        }

    def _normalize_context(
        self,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if not isinstance(context, dict):
            return {}

        return dict(context)

    def _combined_text(
        self,
        goal: dict[str, Any],
        option: dict[str, Any],
    ) -> str:

        parts = [
            goal["original_request"],
            goal["goal"],
            " ".join(
                str(item)
                for item in goal["keywords"]
            ),
            option["name"],
            option["description"],
            " ".join(
                str(item)
                for item in option["assumptions"]
            ),
            " ".join(
                str(item)
                for item in option["execution_plan"]
            ),
        ]

        return " ".join(parts).lower()

    def _find_matches(
        self,
        text: str,
        phrases: set[str],
    ) -> list[str]:

        matches = [
            phrase
            for phrase in phrases
            if phrase.lower() in text
        ]

        return sorted(
            matches
        )

    def _extract_number(
        self,
        context: dict[str, Any],
        keys: list[str],
    ) -> int | None:

        for key in keys:
            if key not in context:
                continue

            value = context[key]

            if isinstance(value, bool):
                continue

            if isinstance(value, int):
                return value

            if isinstance(value, float):
                return int(value)

            if isinstance(value, str):
                try:
                    return int(
                        float(value)
                    )
                except ValueError:
                    continue

        return None

    def _extract_bool(
        self,
        context: dict[str, Any],
        keys: list[str],
    ) -> bool | None:

        for key in keys:
            if key not in context:
                continue

            value = context[key]

            if isinstance(value, bool):
                return value

            if isinstance(value, str):
                normalized = value.strip().lower()

                if normalized in {
                    "true",
                    "yes",
                    "tak",
                    "1",
                }:
                    return True

                if normalized in {
                    "false",
                    "no",
                    "nie",
                    "0",
                }:
                    return False

        return None

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(value, list):
            return list(value)

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, set):
            return list(value)

        if value is None:
            return []

        return [value]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(value, dict):
            return dict(value)

        return {}

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(value).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(text)

        return result

    def _clamp_score(
        self,
        score: float,
    ) -> float:

        return max(
            0.0,
            min(
                5.0,
                float(score),
            ),
        )
