from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class DecisionNodeType(str, Enum):
    START = "START"
    GOAL_ANALYSIS = "GOAL_ANALYSIS"
    RESEARCH_CHECK = "RESEARCH_CHECK"
    RESEARCH = "RESEARCH"
    DEVELOPER_CHECK = "DEVELOPER_CHECK"
    OPTION_GENERATION = "OPTION_GENERATION"
    RISK_EVALUATION = "RISK_EVALUATION"
    STRATEGY_SELECTION = "STRATEGY_SELECTION"
    CONFIRMATION_CHECK = "CONFIRMATION_CHECK"
    CONFIRMATION = "CONFIRMATION"
    EXECUTION = "EXECUTION"
    VALIDATION = "VALIDATION"
    ROLLBACK_CHECK = "ROLLBACK_CHECK"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"
    COMPLETE = "COMPLETE"
    STOP = "STOP"


class DecisionCondition(str, Enum):
    ALWAYS = "ALWAYS"
    YES = "YES"
    NO = "NO"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRED = "REQUIRED"
    NOT_REQUIRED = "NOT_REQUIRED"


class DecisionNodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class DecisionEdge:
    source_id: str
    target_id: str
    condition: str = DecisionCondition.ALWAYS.value
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionNode:
    node_id: str
    node_type: str
    name: str
    description: str
    status: str = DecisionNodeStatus.PENDING.value
    required: bool = True
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionGraphResult:
    graph_id: str
    goal: dict[str, Any]
    start_node_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    execution_order: list[str]
    active_path: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DecisionGraph:

    def __init__(self) -> None:
        self._nodes: dict[str, DecisionNode] = {}
        self._edges: list[DecisionEdge] = []
        self._execution_order: list[str] = []
        self._graph_id = ""

    def build(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        self._reset()

        self._graph_id = f"decision_graph_{uuid4().hex}"

        normalized_goal = self._normalize_goal(goal)

        start_node = self._add_node(
            node_type=DecisionNodeType.START,
            name="Start",
            description="Rozpoczęcie procesu decyzyjnego.",
            required=True,
            input_data={
                "goal": normalized_goal,
            },
        )

        goal_analysis_node = self._add_node(
            node_type=DecisionNodeType.GOAL_ANALYSIS,
            name="Analiza celu",
            description=(
                "Analiza typu celu, priorytetu, złożoności "
                "oraz wymaganych systemów."
            ),
            required=True,
            input_data={
                "goal": normalized_goal,
            },
        )

        research_check_node = self._add_node(
            node_type=DecisionNodeType.RESEARCH_CHECK,
            name="Sprawdzenie potrzeby researchu",
            description=(
                "Ustalenie, czy cel wymaga uruchomienia "
                "Research Agent."
            ),
            required=True,
            input_data={
                "requires_research": normalized_goal[
                    "requires_research"
                ],
            },
        )

        self._add_edge(
            source=start_node,
            target=goal_analysis_node,
        )

        self._add_edge(
            source=goal_analysis_node,
            target=research_check_node,
        )

        previous_node = research_check_node

        if normalized_goal["requires_research"]:
            research_node = self._add_node(
                node_type=DecisionNodeType.RESEARCH,
                name="Research",
                description=(
                    "Analiza projektu, zależności, kodu, "
                    "problemów i możliwych ulepszeń."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            self._add_edge(
                source=research_check_node,
                target=research_node,
                condition=DecisionCondition.YES,
                label="Research wymagany",
            )

            previous_node = research_node

        developer_check_node = self._add_node(
            node_type=DecisionNodeType.DEVELOPER_CHECK,
            name="Sprawdzenie potrzeby zmian w kodzie",
            description=(
                "Ustalenie, czy realizacja celu wymaga "
                "DeveloperController."
            ),
            required=True,
            input_data={
                "requires_developer": normalized_goal[
                    "requires_developer"
                ],
            },
        )

        if normalized_goal["requires_research"]:
            self._add_edge(
                source=previous_node,
                target=developer_check_node,
                condition=DecisionCondition.SUCCESS,
                label="Research zakończony",
            )
        else:
            self._add_edge(
                source=research_check_node,
                target=developer_check_node,
                condition=DecisionCondition.NO,
                label="Research niewymagany",
            )

        previous_node = developer_check_node

        if normalized_goal["requires_developer"]:
            option_generation_node = self._add_node(
                node_type=DecisionNodeType.OPTION_GENERATION,
                name="Generowanie opcji",
                description=(
                    "Przygotowanie kilku możliwych sposobów "
                    "realizacji celu."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            risk_evaluation_node = self._add_node(
                node_type=DecisionNodeType.RISK_EVALUATION,
                name="Ocena ryzyka",
                description=(
                    "Ocena ryzyka technicznego, zakresu zmian "
                    "i wpływu na projekt."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            strategy_selection_node = self._add_node(
                node_type=DecisionNodeType.STRATEGY_SELECTION,
                name="Wybór strategii",
                description=(
                    "Wybór najbezpieczniejszej i najbardziej "
                    "skutecznej strategii."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            confirmation_check_node = self._add_node(
                node_type=DecisionNodeType.CONFIRMATION_CHECK,
                name="Sprawdzenie wymagania akceptacji",
                description=(
                    "Ustalenie, czy przed wykonaniem zmian "
                    "wymagana jest akceptacja użytkownika."
                ),
                required=True,
                input_data={
                    "requires_confirmation": normalized_goal[
                        "requires_confirmation"
                    ],
                },
            )

            self._add_edge(
                source=developer_check_node,
                target=option_generation_node,
                condition=DecisionCondition.YES,
                label="Zmiana kodu wymagana",
            )

            self._add_edge(
                source=option_generation_node,
                target=risk_evaluation_node,
                condition=DecisionCondition.SUCCESS,
            )

            self._add_edge(
                source=risk_evaluation_node,
                target=strategy_selection_node,
                condition=DecisionCondition.SUCCESS,
            )

            self._add_edge(
                source=strategy_selection_node,
                target=confirmation_check_node,
                condition=DecisionCondition.SUCCESS,
            )

            previous_node = confirmation_check_node

            if normalized_goal["requires_confirmation"]:
                confirmation_node = self._add_node(
                    node_type=DecisionNodeType.CONFIRMATION,
                    name="Akceptacja użytkownika",
                    description=(
                        "Prezentacja strategii i patch preview "
                        "przed wykonaniem zmian."
                    ),
                    required=True,
                    input_data={
                        "goal": normalized_goal,
                    },
                )

                self._add_edge(
                    source=confirmation_check_node,
                    target=confirmation_node,
                    condition=DecisionCondition.YES,
                    label="Akceptacja wymagana",
                )

                previous_node = confirmation_node

            execution_node = self._add_node(
                node_type=DecisionNodeType.EXECUTION,
                name="Wykonanie strategii",
                description=(
                    "Uruchomienie DeveloperController "
                    "i wykonanie zatwierdzonych zmian."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            if normalized_goal["requires_confirmation"]:
                self._add_edge(
                    source=previous_node,
                    target=execution_node,
                    condition=DecisionCondition.APPROVED,
                    label="Zmiana zaakceptowana",
                )
            else:
                self._add_edge(
                    source=confirmation_check_node,
                    target=execution_node,
                    condition=DecisionCondition.NO,
                    label="Akceptacja niewymagana",
                )

            validation_node = self._add_node(
                node_type=DecisionNodeType.VALIDATION,
                name="Walidacja",
                description=(
                    "Sprawdzenie składni, importów "
                    "i poprawności wykonanych zmian."
                ),
                required=True,
            )

            rollback_check_node = self._add_node(
                node_type=DecisionNodeType.ROLLBACK_CHECK,
                name="Sprawdzenie rollbacku",
                description=(
                    "Ustalenie, czy wynik walidacji "
                    "wymaga przywrócenia backupu."
                ),
                required=True,
            )

            rollback_node = self._add_node(
                node_type=DecisionNodeType.ROLLBACK,
                name="Rollback",
                description=(
                    "Przywrócenie poprzedniej wersji plików "
                    "po nieudanej walidacji."
                ),
                required=False,
            )

            report_node = self._add_node(
                node_type=DecisionNodeType.REPORT,
                name="Raport wykonania",
                description=(
                    "Przygotowanie raportu ze zmian, walidacji "
                    "i ewentualnego rollbacku."
                ),
                required=True,
            )

            complete_node = self._add_node(
                node_type=DecisionNodeType.COMPLETE,
                name="Zakończenie",
                description=(
                    "Proces decyzyjny i wykonawczy zakończony."
                ),
                required=True,
            )

            self._add_edge(
                source=execution_node,
                target=validation_node,
                condition=DecisionCondition.SUCCESS,
            )

            self._add_edge(
                source=validation_node,
                target=rollback_check_node,
                condition=DecisionCondition.ALWAYS,
            )

            self._add_edge(
                source=rollback_check_node,
                target=rollback_node,
                condition=DecisionCondition.YES,
                label="Rollback wymagany",
            )

            self._add_edge(
                source=rollback_check_node,
                target=report_node,
                condition=DecisionCondition.NO,
                label="Rollback niewymagany",
            )

            self._add_edge(
                source=rollback_node,
                target=report_node,
                condition=DecisionCondition.SUCCESS,
            )

            self._add_edge(
                source=report_node,
                target=complete_node,
                condition=DecisionCondition.SUCCESS,
            )

        else:
            report_node = self._add_node(
                node_type=DecisionNodeType.REPORT,
                name="Raport odpowiedzi",
                description=(
                    "Przygotowanie odpowiedzi lub raportu "
                    "bez wykonywania zmian w kodzie."
                ),
                required=True,
                input_data={
                    "goal": normalized_goal,
                },
            )

            complete_node = self._add_node(
                node_type=DecisionNodeType.COMPLETE,
                name="Zakończenie",
                description=(
                    "Proces analizy zakończony bez zmian "
                    "w projekcie."
                ),
                required=True,
            )

            self._add_edge(
                source=developer_check_node,
                target=report_node,
                condition=DecisionCondition.NO,
                label="DeveloperController niewymagany",
            )

            self._add_edge(
                source=report_node,
                target=complete_node,
                condition=DecisionCondition.SUCCESS,
            )

        active_path = self._build_default_active_path(
            normalized_goal
        )

        result = DecisionGraphResult(
            graph_id=self._graph_id,
            goal=normalized_goal,
            start_node_id=start_node.node_id,
            nodes=[
                node.to_dict()
                for node in self._nodes.values()
            ],
            edges=[
                edge.to_dict()
                for edge in self._edges
            ],
            execution_order=self._execution_order.copy(),
            active_path=active_path,
            metadata={
                "graph_version": "1.0.0",
                "nodes_count": len(self._nodes),
                "edges_count": len(self._edges),
                "requires_research": normalized_goal[
                    "requires_research"
                ],
                "requires_developer": normalized_goal[
                    "requires_developer"
                ],
                "requires_confirmation": normalized_goal[
                    "requires_confirmation"
                ],
            },
        )

        return result.to_dict()

    def create(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        return self.build(goal)

    def generate(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        return self.build(goal)

    def get_node(
        self,
        node_id: str,
    ) -> dict[str, Any] | None:

        node = self._nodes.get(node_id)

        if node is None:
            return None

        return node.to_dict()

    def get_nodes_by_type(
        self,
        node_type: str,
    ) -> list[dict[str, Any]]:

        return [
            node.to_dict()
            for node in self._nodes.values()
            if node.node_type == node_type
        ]

    def get_outgoing_edges(
        self,
        node_id: str,
    ) -> list[dict[str, Any]]:

        return [
            edge.to_dict()
            for edge in self._edges
            if edge.source_id == node_id
        ]

    def update_node_status(
        self,
        node_id: str,
        status: str,
        output_data: dict[str, Any] | None = None,
    ) -> bool:

        node = self._nodes.get(node_id)

        if node is None:
            return False

        valid_statuses = {
            item.value
            for item in DecisionNodeStatus
        }

        if status not in valid_statuses:
            return False

        node.status = status

        if output_data is not None:
            node.output_data = output_data

        return True

    def _add_node(
        self,
        node_type: DecisionNodeType,
        name: str,
        description: str,
        required: bool,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionNode:

        node_id = (
            f"{node_type.value.lower()}_"
            f"{uuid4().hex[:10]}"
        )

        node = DecisionNode(
            node_id=node_id,
            node_type=node_type.value,
            name=name,
            description=description,
            required=required,
            input_data=input_data or {},
            metadata=metadata or {},
        )

        self._nodes[node_id] = node
        self._execution_order.append(node_id)

        return node

    def _add_edge(
        self,
        source: DecisionNode,
        target: DecisionNode,
        condition: DecisionCondition = (
            DecisionCondition.ALWAYS
        ),
        label: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEdge:

        edge = DecisionEdge(
            source_id=source.node_id,
            target_id=target.node_id,
            condition=condition.value,
            label=label,
            metadata=metadata or {},
        )

        self._edges.append(edge)

        return edge

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(goal, dict):
            raise TypeError(
                "DecisionGraph wymaga celu typu dict."
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
            ),
            "priority": str(
                goal.get(
                    "priority",
                    "LOW",
                )
            ),
            "complexity": str(
                goal.get(
                    "complexity",
                    "LOW",
                )
            ),
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

    def _build_default_active_path(
        self,
        goal: dict[str, Any],
    ) -> list[str]:

        active_types = [
            DecisionNodeType.START.value,
            DecisionNodeType.GOAL_ANALYSIS.value,
            DecisionNodeType.RESEARCH_CHECK.value,
        ]

        if goal["requires_research"]:
            active_types.append(
                DecisionNodeType.RESEARCH.value
            )

        active_types.append(
            DecisionNodeType.DEVELOPER_CHECK.value
        )

        if goal["requires_developer"]:
            active_types.extend(
                [
                    DecisionNodeType.OPTION_GENERATION.value,
                    DecisionNodeType.RISK_EVALUATION.value,
                    DecisionNodeType.STRATEGY_SELECTION.value,
                    DecisionNodeType.CONFIRMATION_CHECK.value,
                ]
            )

            if goal["requires_confirmation"]:
                active_types.append(
                    DecisionNodeType.CONFIRMATION.value
                )

            active_types.extend(
                [
                    DecisionNodeType.EXECUTION.value,
                    DecisionNodeType.VALIDATION.value,
                    DecisionNodeType.ROLLBACK_CHECK.value,
                    DecisionNodeType.REPORT.value,
                    DecisionNodeType.COMPLETE.value,
                ]
            )

        else:
            active_types.extend(
                [
                    DecisionNodeType.REPORT.value,
                    DecisionNodeType.COMPLETE.value,
                ]
            )

        active_path: list[str] = []

        for node_id in self._execution_order:
            node = self._nodes[node_id]

            if node.node_type in active_types:
                active_path.append(node_id)

        return active_path

    def _reset(self) -> None:
        self._nodes = {}
        self._edges = []
        self._execution_order = []
        self._graph_id = ""