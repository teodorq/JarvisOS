from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class StrategyType(str, Enum):
    MINIMAL_CHANGE = "MINIMAL_CHANGE"
    SAFE_FIX = "SAFE_FIX"
    TARGETED_REFACTOR = "TARGETED_REFACTOR"
    FULL_REFACTOR = "FULL_REFACTOR"
    FEATURE_EXTENSION = "FEATURE_EXTENSION"
    RESEARCH_FIRST = "RESEARCH_FIRST"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"
    DIRECT_RESPONSE = "DIRECT_RESPONSE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class StrategyScope(str, Enum):
    SINGLE_FILE = "SINGLE_FILE"
    MODULE = "MODULE"
    MULTI_MODULE = "MULTI_MODULE"
    PROJECT = "PROJECT"
    NONE = "NONE"


class StrategyEffort(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class ReasoningOption:
    option_id: str
    name: str
    description: str
    strategy_type: str
    scope: str
    effort: str
    requires_research: bool
    requires_developer: bool
    requires_confirmation: bool
    estimated_steps: int
    expected_benefits: list[str] = field(default_factory=list)
    expected_drawbacks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    execution_plan: list[str] = field(default_factory=list)
    score_hint: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptionGenerationResult:
    generation_id: str
    goal: dict[str, Any]
    options: list[dict[str, Any]]
    recommended_option_id: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OptionGenerator:

    def generate(
        self,
        goal: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_goal = self._normalize_goal(goal)
        normalized_research = self._normalize_research_context(
            research_context
        )

        options: list[ReasoningOption] = []

        goal_type = normalized_goal["goal_type"]
        complexity = normalized_goal["complexity"]
        requires_research = normalized_goal[
            "requires_research"
        ]
        requires_developer = normalized_goal[
            "requires_developer"
        ]
        requires_confirmation = normalized_goal[
            "requires_confirmation"
        ]

        if not requires_developer:
            options.extend(
                self._build_non_developer_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        elif goal_type == "BUG_FIX":
            options.extend(
                self._build_bug_fix_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        elif goal_type == "REFACTOR":
            options.extend(
                self._build_refactor_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        elif goal_type == "FEATURE":
            options.extend(
                self._build_feature_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        elif goal_type == "CODE_IMPROVEMENT":
            options.extend(
                self._build_improvement_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        else:
            options.extend(
                self._build_generic_developer_options(
                    normalized_goal,
                    normalized_research,
                )
            )

        options = self._deduplicate_options(options)
        options = self._limit_options(options, limit=5)

        recommended_option_id = (
            self._select_initial_recommendation(options)
        )

        result = OptionGenerationResult(
            generation_id=(
                f"option_generation_{uuid4().hex}"
            ),
            goal=normalized_goal,
            options=[
                option.to_dict()
                for option in options
            ],
            recommended_option_id=recommended_option_id,
            metadata={
                "generator_version": "1.0.0",
                "options_count": len(options),
                "goal_type": goal_type,
                "complexity": complexity,
                "requires_research": requires_research,
                "requires_developer": requires_developer,
                "requires_confirmation": (
                    requires_confirmation
                ),
                "decision_graph_id": (
                    decision_graph.get("graph_id")
                    if isinstance(
                        decision_graph,
                        dict,
                    )
                    else None
                ),
                "research_available": bool(
                    normalized_research
                ),
            },
        )

        return result.to_dict()

    def create_options(
        self,
        goal: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.generate(
            goal=goal,
            decision_graph=decision_graph,
            research_context=research_context,
        )

    def build(
        self,
        goal: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.generate(
            goal=goal,
            decision_graph=decision_graph,
            research_context=research_context,
        )

    def _build_non_developer_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        options: list[ReasoningOption] = []

        if goal["requires_research"]:
            options.append(
                self._make_option(
                    name="Research i raport",
                    description=(
                        "Przeprowadzić analizę oraz przygotować "
                        "raport bez wykonywania zmian w kodzie."
                    ),
                    strategy_type=(
                        StrategyType.RESEARCH_FIRST
                    ),
                    scope=StrategyScope.NONE,
                    effort=StrategyEffort.MEDIUM,
                    requires_research=True,
                    requires_developer=False,
                    requires_confirmation=False,
                    estimated_steps=4,
                    expected_benefits=[
                        "Brak ryzyka modyfikacji projektu.",
                        "Lepsze rozpoznanie problemu.",
                        "Gotowe rekomendacje do dalszych działań.",
                    ],
                    expected_drawbacks=[
                        "Problem nie zostanie automatycznie naprawiony.",
                    ],
                    assumptions=[
                        "Użytkownik oczekuje analizy lub odpowiedzi.",
                    ],
                    execution_plan=[
                        "Uruchomić ResearchWorkflow.",
                        "Zebrać problemy i zależności.",
                        "Porównać możliwe rozwiązania.",
                        "Przygotować raport końcowy.",
                    ],
                    score_hint=0.91,
                )
            )

        options.append(
            self._make_option(
                name="Bezpośrednia odpowiedź",
                description=(
                    "Przygotować odpowiedź na podstawie "
                    "dostępnego kontekstu bez zmian w projekcie."
                ),
                strategy_type=(
                    StrategyType.DIRECT_RESPONSE
                ),
                scope=StrategyScope.NONE,
                effort=StrategyEffort.LOW,
                requires_research=False,
                requires_developer=False,
                requires_confirmation=False,
                estimated_steps=2,
                expected_benefits=[
                    "Najszybszy czas realizacji.",
                    "Brak ingerencji w kod.",
                ],
                expected_drawbacks=[
                    "Mniejsza dokładność przy złożonych celach.",
                ],
                assumptions=[
                    "Cel nie wymaga zmian w plikach.",
                ],
                execution_plan=[
                    "Przeanalizować cel.",
                    "Przygotować odpowiedź lub raport.",
                ],
                score_hint=0.72,
            )
        )

        if research_context:
            options.append(
                self._make_option(
                    name="Odpowiedź oparta na researchu",
                    description=(
                        "Wykorzystać istniejący research "
                        "i przygotować końcową rekomendację."
                    ),
                    strategy_type=(
                        StrategyType.ANALYSIS_ONLY
                    ),
                    scope=StrategyScope.NONE,
                    effort=StrategyEffort.LOW,
                    requires_research=False,
                    requires_developer=False,
                    requires_confirmation=False,
                    estimated_steps=2,
                    expected_benefits=[
                        "Wykorzystanie już zebranych danych.",
                        "Brak dodatkowego kosztu analizy.",
                    ],
                    expected_drawbacks=[
                        "Jakość zależy od aktualności researchu.",
                    ],
                    assumptions=[
                        "Research zawiera wystarczające dane.",
                    ],
                    execution_plan=[
                        "Odczytać ResearchContext.",
                        "Przygotować końcową rekomendację.",
                    ],
                    score_hint=0.86,
                )
            )

        return options

    def _build_bug_fix_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        options: list[ReasoningOption] = [
            self._make_option(
                name="Minimalna naprawa",
                description=(
                    "Zmienić wyłącznie kod bezpośrednio "
                    "odpowiedzialny za wykryty błąd."
                ),
                strategy_type=(
                    StrategyType.MINIMAL_CHANGE
                ),
                scope=self._infer_scope(goal),
                effort=StrategyEffort.LOW,
                requires_research=False,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=5,
                expected_benefits=[
                    "Mały zakres zmian.",
                    "Niskie ryzyko efektów ubocznych.",
                    "Łatwy rollback.",
                ],
                expected_drawbacks=[
                    "Może nie usuwać przyczyny architektonicznej.",
                    "Możliwa konieczność kolejnej poprawki.",
                ],
                assumptions=[
                    "Źródło błędu jest dobrze rozpoznane.",
                ],
                execution_plan=[
                    "Zlokalizować źródło błędu.",
                    "Przygotować minimalny patch.",
                    "Pokazać Patch Preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.93,
            ),
            self._make_option(
                name="Bezpieczna naprawa z analizą zależności",
                description=(
                    "Przeanalizować zależności modułu, "
                    "a następnie naprawić błąd i miejsca powiązane."
                ),
                strategy_type=StrategyType.SAFE_FIX,
                scope=self._infer_scope(
                    goal,
                    prefer_module=True,
                ),
                effort=StrategyEffort.MEDIUM,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=8,
                expected_benefits=[
                    "Usunięcie błędu wraz z przyczyną.",
                    "Kontrola wpływu na zależności.",
                    "Większa stabilność rozwiązania.",
                ],
                expected_drawbacks=[
                    "Większy zakres zmian.",
                    "Dłuższy proces walidacji.",
                ],
                assumptions=[
                    "Research Agent może przeanalizować zależności.",
                ],
                execution_plan=[
                    "Uruchomić analizę projektu.",
                    "Zbudować graf zależności.",
                    "Znaleźć źródło i skutki błędu.",
                    "Przygotować patch.",
                    "Pokazać Patch Preview.",
                    "Wykonać backup.",
                    "Wykonać zmianę.",
                    "Uruchomić pełną walidację.",
                ],
                score_hint=0.88,
            ),
        ]

        if goal["complexity"] == "HIGH":
            options.append(
                self._make_option(
                    name="Refaktoryzacja problematycznego obszaru",
                    description=(
                        "Przebudować większy fragment systemu, "
                        "jeżeli błąd wynika z jego architektury."
                    ),
                    strategy_type=(
                        StrategyType.TARGETED_REFACTOR
                    ),
                    scope=StrategyScope.MULTI_MODULE,
                    effort=StrategyEffort.HIGH,
                    requires_research=True,
                    requires_developer=True,
                    requires_confirmation=True,
                    estimated_steps=12,
                    expected_benefits=[
                        "Usunięcie głównej przyczyny problemu.",
                        "Lepsza jakość architektury.",
                        "Mniejsze ryzyko podobnych błędów.",
                    ],
                    expected_drawbacks=[
                        "Wysokie ryzyko regresji.",
                        "Duży zakres zmian.",
                        "Wymaga szerokiej walidacji.",
                    ],
                    assumptions=[
                        "Problem ma charakter architektoniczny.",
                    ],
                    execution_plan=[
                        "Przeanalizować cały problematyczny obszar.",
                        "Zaprojektować nową strukturę.",
                        "Określić wpływ zmian.",
                        "Przygotować plan migracji.",
                        "Wygenerować patch.",
                        "Pokazać Patch Preview.",
                        "Wykonać backup.",
                        "Wdrożyć zmiany etapami.",
                        "Zweryfikować składnię.",
                        "Zweryfikować importy.",
                        "Uruchomić testy.",
                        "Przygotować raport.",
                    ],
                    score_hint=0.62,
                )
            )

        if not research_context:
            options.append(
                self._build_manual_review_option(goal)
            )

        return options

    def _build_refactor_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        options: list[ReasoningOption] = [
            self._make_option(
                name="Refaktoryzacja punktowa",
                description=(
                    "Uporządkować wyłącznie wskazaną klasę "
                    "lub moduł bez zmiany publicznego interfejsu."
                ),
                strategy_type=(
                    StrategyType.TARGETED_REFACTOR
                ),
                scope=self._infer_scope(
                    goal,
                    prefer_module=True,
                ),
                effort=StrategyEffort.MEDIUM,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=8,
                expected_benefits=[
                    "Kontrolowany zakres zmian.",
                    "Zachowanie zgodności z resztą systemu.",
                    "Lepsza czytelność kodu.",
                ],
                expected_drawbacks=[
                    "Nie rozwiązuje problemów poza wskazanym obszarem.",
                ],
                assumptions=[
                    "Publiczne API modułu może pozostać bez zmian.",
                ],
                execution_plan=[
                    "Przeanalizować moduł.",
                    "Znaleźć duplikację i sprzężenia.",
                    "Zaprojektować bezpieczny refaktor.",
                    "Sprawdzić zależności.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.91,
            ),
            self._make_option(
                name="Pełna refaktoryzacja obszaru",
                description=(
                    "Przebudować cały powiązany obszar projektu "
                    "wraz z zależnościami."
                ),
                strategy_type=(
                    StrategyType.FULL_REFACTOR
                ),
                scope=StrategyScope.MULTI_MODULE,
                effort=StrategyEffort.HIGH,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=13,
                expected_benefits=[
                    "Spójna architektura.",
                    "Redukcja długu technicznego.",
                    "Lepsza rozszerzalność.",
                ],
                expected_drawbacks=[
                    "Duże ryzyko regresji.",
                    "Wysoki koszt wykonania.",
                    "Większy patch.",
                ],
                assumptions=[
                    "Obszar wymaga zmian w wielu modułach.",
                ],
                execution_plan=[
                    "Zbudować mapę zależności.",
                    "Przeanalizować publiczne interfejsy.",
                    "Wyznaczyć granice refaktoru.",
                    "Zaprojektować nową architekturę.",
                    "Przygotować plan migracji.",
                    "Wygenerować patch.",
                    "Pokazać Patch Preview.",
                    "Wykonać backup.",
                    "Wprowadzić zmiany.",
                    "Zweryfikować składnię.",
                    "Zweryfikować importy.",
                    "Uruchomić testy.",
                    "Przygotować raport.",
                ],
                score_hint=0.68,
            ),
            self._make_option(
                name="Minimalne uporządkowanie",
                description=(
                    "Wprowadzić tylko drobne poprawki jakościowe "
                    "bez przebudowy architektury."
                ),
                strategy_type=(
                    StrategyType.MINIMAL_CHANGE
                ),
                scope=self._infer_scope(goal),
                effort=StrategyEffort.LOW,
                requires_research=False,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=5,
                expected_benefits=[
                    "Bardzo małe ryzyko.",
                    "Szybkie wdrożenie.",
                ],
                expected_drawbacks=[
                    "Ograniczona poprawa jakości.",
                    "Dług techniczny może pozostać.",
                ],
                assumptions=[
                    "Cel można osiągnąć bez zmiany architektury.",
                ],
                execution_plan=[
                    "Znaleźć proste problemy jakościowe.",
                    "Przygotować mały patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.79,
            ),
        ]

        if not research_context:
            options.append(
                self._build_manual_review_option(goal)
            )

        return options

    def _build_feature_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        options: list[ReasoningOption] = [
            self._make_option(
                name="Minimalna wersja funkcji",
                description=(
                    "Dodać najmniejszy kompletny zakres nowej "
                    "funkcjonalności zgodny z obecnym interfejsem."
                ),
                strategy_type=(
                    StrategyType.FEATURE_EXTENSION
                ),
                scope=self._infer_scope(goal),
                effort=StrategyEffort.MEDIUM,
                requires_research=goal[
                    "requires_research"
                ],
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=7,
                expected_benefits=[
                    "Szybkie dostarczenie funkcji.",
                    "Ograniczony zakres zmian.",
                    "Łatwiejsze testowanie.",
                ],
                expected_drawbacks=[
                    "Mniejszy zakres możliwości.",
                    "Może wymagać późniejszego rozszerzenia.",
                ],
                assumptions=[
                    "Nową funkcję można dodać do obecnej architektury.",
                ],
                execution_plan=[
                    "Przeanalizować wymagania.",
                    "Sprawdzić punkty integracji.",
                    "Zaprojektować minimalne API.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.9,
            ),
            self._make_option(
                name="Pełna integracja funkcji",
                description=(
                    "Dodać funkcjonalność wraz z pełną integracją "
                    "z istniejącymi modułami i workflow."
                ),
                strategy_type=(
                    StrategyType.FEATURE_EXTENSION
                ),
                scope=StrategyScope.MULTI_MODULE,
                effort=StrategyEffort.HIGH,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=11,
                expected_benefits=[
                    "Kompletna funkcjonalność.",
                    "Spójność z architekturą projektu.",
                    "Lepsza gotowość do dalszego rozwoju.",
                ],
                expected_drawbacks=[
                    "Większy zakres zmian.",
                    "Większe ryzyko regresji.",
                ],
                assumptions=[
                    "Funkcja wymaga integracji z wieloma modułami.",
                ],
                execution_plan=[
                    "Przeanalizować wymagania.",
                    "Zbudować mapę integracji.",
                    "Sprawdzić zależności.",
                    "Zaprojektować API.",
                    "Przygotować implementację.",
                    "Wygenerować patch.",
                    "Pokazać Patch Preview.",
                    "Wykonać backup.",
                    "Wdrożyć zmianę.",
                    "Uruchomić walidację.",
                    "Przygotować raport.",
                ],
                score_hint=0.76,
            ),
            self._make_option(
                name="Research przed implementacją",
                description=(
                    "Najpierw przeanalizować możliwe podejścia, "
                    "a dopiero później wybrać implementację."
                ),
                strategy_type=(
                    StrategyType.RESEARCH_FIRST
                ),
                scope=self._infer_scope(
                    goal,
                    prefer_module=True,
                ),
                effort=StrategyEffort.MEDIUM,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=8,
                expected_benefits=[
                    "Lepszy wybór architektury.",
                    "Niższe ryzyko błędnej integracji.",
                ],
                expected_drawbacks=[
                    "Dłuższy proces przed implementacją.",
                ],
                assumptions=[
                    "Istnieje kilka sensownych sposobów implementacji.",
                ],
                execution_plan=[
                    "Uruchomić ResearchWorkflow.",
                    "Porównać podejścia.",
                    "Ocenić wpływ na projekt.",
                    "Wybrać rozwiązanie.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.87,
            ),
        ]

        return options

    def _build_improvement_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        options: list[ReasoningOption] = [
            self._make_option(
                name="Bezpieczne ulepszenie punktowe",
                description=(
                    "Ulepszyć wskazany obszar przy minimalnej "
                    "liczbie zmian."
                ),
                strategy_type=(
                    StrategyType.MINIMAL_CHANGE
                ),
                scope=self._infer_scope(goal),
                effort=StrategyEffort.LOW,
                requires_research=False,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=5,
                expected_benefits=[
                    "Małe ryzyko.",
                    "Szybka poprawa jakości.",
                ],
                expected_drawbacks=[
                    "Ograniczony efekt.",
                ],
                assumptions=[
                    "Poprawa nie wymaga zmian architektonicznych.",
                ],
                execution_plan=[
                    "Znaleźć najważniejszy punkt poprawy.",
                    "Przygotować mały patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.88,
            ),
            self._make_option(
                name="Ulepszenie oparte na analizie projektu",
                description=(
                    "Przeprowadzić research i zoptymalizować "
                    "najważniejsze elementy wskazanego obszaru."
                ),
                strategy_type=StrategyType.SAFE_FIX,
                scope=self._infer_scope(
                    goal,
                    prefer_module=True,
                ),
                effort=StrategyEffort.MEDIUM,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=9,
                expected_benefits=[
                    "Lepsze dopasowanie zmian do projektu.",
                    "Kontrola wpływu na zależności.",
                    "Większy efekt końcowy.",
                ],
                expected_drawbacks=[
                    "Większy zakres zmian.",
                ],
                assumptions=[
                    "Research Agent może wskazać priorytetowe poprawki.",
                ],
                execution_plan=[
                    "Przeanalizować projekt.",
                    "Wykryć główne problemy.",
                    "Uszeregować poprawki.",
                    "Wybrać bezpieczny zakres.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać backup.",
                    "Wdrożyć zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.92,
            ),
            self._make_option(
                name="Kompleksowa modernizacja",
                description=(
                    "Przebudować większy obszar projektu "
                    "w celu poprawy jakości i rozszerzalności."
                ),
                strategy_type=(
                    StrategyType.FULL_REFACTOR
                ),
                scope=StrategyScope.MULTI_MODULE,
                effort=StrategyEffort.HIGH,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=12,
                expected_benefits=[
                    "Duża poprawa jakości.",
                    "Lepsza architektura.",
                    "Większa skalowalność.",
                ],
                expected_drawbacks=[
                    "Wysokie ryzyko regresji.",
                    "Duży koszt wykonania.",
                ],
                assumptions=[
                    "Obecna architektura ogranicza dalszy rozwój.",
                ],
                execution_plan=[
                    "Przeanalizować cały obszar.",
                    "Zbudować graf zależności.",
                    "Wyznaczyć problemy architektoniczne.",
                    "Przygotować projekt zmian.",
                    "Ocenić wpływ.",
                    "Wygenerować patch.",
                    "Pokazać preview.",
                    "Wykonać backup.",
                    "Wdrożyć zmianę.",
                    "Zweryfikować importy.",
                    "Uruchomić testy.",
                    "Przygotować raport.",
                ],
                score_hint=0.66,
            ),
        ]

        return options

    def _build_generic_developer_options(
        self,
        goal: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[ReasoningOption]:

        return [
            self._make_option(
                name="Minimalna bezpieczna zmiana",
                description=(
                    "Zrealizować cel przy najmniejszym możliwym "
                    "zakresie zmian."
                ),
                strategy_type=(
                    StrategyType.MINIMAL_CHANGE
                ),
                scope=self._infer_scope(goal),
                effort=StrategyEffort.LOW,
                requires_research=False,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=5,
                expected_benefits=[
                    "Małe ryzyko.",
                    "Łatwy rollback.",
                ],
                expected_drawbacks=[
                    "Ograniczona kompletność rozwiązania.",
                ],
                assumptions=[
                    "Cel można zrealizować małym patchem.",
                ],
                execution_plan=[
                    "Przeanalizować cel.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać zmianę.",
                    "Uruchomić walidację.",
                ],
                score_hint=0.82,
            ),
            self._make_option(
                name="Pełne rozwiązanie z researchem",
                description=(
                    "Przeprowadzić analizę, a następnie wdrożyć "
                    "pełne rozwiązanie."
                ),
                strategy_type=StrategyType.SAFE_FIX,
                scope=self._infer_scope(
                    goal,
                    prefer_module=True,
                ),
                effort=StrategyEffort.MEDIUM,
                requires_research=True,
                requires_developer=True,
                requires_confirmation=True,
                estimated_steps=9,
                expected_benefits=[
                    "Lepsza kompletność rozwiązania.",
                    "Kontrola wpływu na projekt.",
                ],
                expected_drawbacks=[
                    "Większy zakres i koszt zmian.",
                ],
                assumptions=[
                    "Research zwiększy jakość decyzji.",
                ],
                execution_plan=[
                    "Uruchomić research.",
                    "Przeanalizować zależności.",
                    "Wybrać sposób realizacji.",
                    "Przygotować patch.",
                    "Pokazać preview.",
                    "Wykonać backup.",
                    "Wdrożyć zmianę.",
                    "Uruchomić walidację.",
                    "Przygotować raport.",
                ],
                score_hint=0.89,
            ),
            self._build_manual_review_option(goal),
        ]

    def _build_manual_review_option(
        self,
        goal: dict[str, Any],
    ) -> ReasoningOption:

        return self._make_option(
            name="Ręczna analiza przed zmianą",
            description=(
                "Zatrzymać automatyczne wykonanie i przygotować "
                "raport do ręcznej decyzji użytkownika."
            ),
            strategy_type=StrategyType.MANUAL_REVIEW,
            scope=self._infer_scope(goal),
            effort=StrategyEffort.LOW,
            requires_research=True,
            requires_developer=False,
            requires_confirmation=True,
            estimated_steps=3,
            expected_benefits=[
                "Brak automatycznego ryzyka.",
                "Pełna kontrola użytkownika.",
            ],
            expected_drawbacks=[
                "Brak automatycznej naprawy.",
                "Wymaga decyzji ręcznej.",
            ],
            assumptions=[
                "Automatyczna zmiana może być zbyt ryzykowna.",
            ],
            execution_plan=[
                "Przeanalizować problem.",
                "Przygotować raport.",
                "Przekazać decyzję użytkownikowi.",
            ],
            score_hint=0.55,
        )

    def _make_option(
        self,
        name: str,
        description: str,
        strategy_type: StrategyType,
        scope: StrategyScope,
        effort: StrategyEffort,
        requires_research: bool,
        requires_developer: bool,
        requires_confirmation: bool,
        estimated_steps: int,
        expected_benefits: list[str],
        expected_drawbacks: list[str],
        assumptions: list[str],
        execution_plan: list[str],
        score_hint: float,
    ) -> ReasoningOption:

        return ReasoningOption(
            option_id=f"option_{uuid4().hex}",
            name=name,
            description=description,
            strategy_type=strategy_type.value,
            scope=scope.value,
            effort=effort.value,
            requires_research=requires_research,
            requires_developer=requires_developer,
            requires_confirmation=requires_confirmation,
            estimated_steps=estimated_steps,
            expected_benefits=expected_benefits,
            expected_drawbacks=expected_drawbacks,
            assumptions=assumptions,
            execution_plan=execution_plan,
            score_hint=round(
                max(
                    0.0,
                    min(
                        1.0,
                        score_hint,
                    ),
                ),
                2,
            ),
            metadata={
                "generator_version": "1.0.0",
            },
        )

    def _infer_scope(
        self,
        goal: dict[str, Any],
        prefer_module: bool = False,
    ) -> StrategyScope:

        complexity = goal["complexity"]
        detected_modules = goal["detected_modules"]

        if complexity == "HIGH":
            return StrategyScope.MULTI_MODULE

        if len(detected_modules) >= 2:
            return StrategyScope.MULTI_MODULE

        if len(detected_modules) == 1:
            return StrategyScope.MODULE

        if prefer_module:
            return StrategyScope.MODULE

        if complexity == "LOW":
            return StrategyScope.SINGLE_FILE

        return StrategyScope.MODULE

    def _select_initial_recommendation(
        self,
        options: list[ReasoningOption],
    ) -> str | None:

        if not options:
            return None

        recommended = max(
            options,
            key=lambda option: option.score_hint,
        )

        return recommended.option_id

    def _deduplicate_options(
        self,
        options: list[ReasoningOption],
    ) -> list[ReasoningOption]:

        unique_options: list[ReasoningOption] = []
        seen: set[tuple[str, str]] = set()

        for option in options:
            key = (
                option.strategy_type,
                option.name.lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique_options.append(option)

        return unique_options

    def _limit_options(
        self,
        options: list[ReasoningOption],
        limit: int,
    ) -> list[ReasoningOption]:

        sorted_options = sorted(
            options,
            key=lambda option: option.score_hint,
            reverse=True,
        )

        return sorted_options[:limit]

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(goal, dict):
            raise TypeError(
                "OptionGenerator wymaga celu typu dict."
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
            "confidence": float(
                goal.get(
                    "confidence",
                    0.0,
                )
            ),
            "keywords": list(
                goal.get(
                    "keywords",
                    [],
                )
            ),
            "detected_modules": list(
                goal.get(
                    "detected_modules",
                    [],
                )
            ),
            "metadata": dict(
                goal.get(
                    "metadata",
                    {},
                )
            ),
        }

    def _normalize_research_context(
        self,
        research_context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if not isinstance(
            research_context,
            dict,
        ):
            return {}

        return dict(research_context)