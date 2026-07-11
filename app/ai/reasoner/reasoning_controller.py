from __future__ import annotations

from typing import Any

from app.ai.reasoner.decision_graph import DecisionGraph
from app.ai.reasoner.goal_reasoner import GoalReasoner
from app.ai.reasoner.option_generator import OptionGenerator
from app.ai.reasoner.reasoning_memory import ReasoningMemory
from app.ai.reasoner.reasoning_session import ReasoningSession
from app.ai.reasoner.risk_evaluator import RiskEvaluator
from app.ai.reasoner.strategy_builder import StrategyBuilder


class ReasoningController:

    def __init__(
        self,
        goal_reasoner: GoalReasoner | None = None,
        decision_graph: DecisionGraph | None = None,
        option_generator: OptionGenerator | None = None,
        risk_evaluator: RiskEvaluator | None = None,
        strategy_builder: StrategyBuilder | None = None,
        reasoning_memory: ReasoningMemory | None = None,
        research_service: Any | None = None,
        developer_controller: Any | None = None,
    ) -> None:

        self.goal_reasoner = (
            goal_reasoner
            if goal_reasoner is not None
            else GoalReasoner()
        )

        self.decision_graph = (
            decision_graph
            if decision_graph is not None
            else DecisionGraph()
        )

        self.option_generator = (
            option_generator
            if option_generator is not None
            else OptionGenerator()
        )

        self.risk_evaluator = (
            risk_evaluator
            if risk_evaluator is not None
            else RiskEvaluator()
        )

        self.strategy_builder = (
            strategy_builder
            if strategy_builder is not None
            else StrategyBuilder()
        )

        self.reasoning_memory = (
            reasoning_memory
            if reasoning_memory is not None
            else ReasoningMemory()
        )

        self.research_service = research_service
        self.developer_controller = developer_controller

        self._sessions: dict[str, ReasoningSession] = {}

    def reason(
        self,
        user_request: str,
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
        auto_execute: bool = False,
        approved: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        session = ReasoningSession(
            user_request=user_request,
            metadata=metadata,
        )

        self._sessions[session.session_id] = session
        session.start()

        try:
            goal = self.goal_reasoner.reason(
                user_request
            )
            session.set_goal(goal)

            graph = self.decision_graph.build(
                goal
            )
            session.set_decision_graph(graph)

            resolved_research = self._resolve_research_context(
                goal=goal,
                user_request=user_request,
                research_context=research_context,
            )

            if resolved_research:
                session.set_research_context(
                    resolved_research
                )

            options_result = self.option_generator.generate(
                goal=goal,
                decision_graph=graph,
                research_context=resolved_research,
            )
            session.set_options_result(
                options_result
            )

            risk_result = self.risk_evaluator.evaluate(
                goal=goal,
                options_result=options_result,
                research_context=resolved_research,
                project_context=project_context,
            )
            session.set_risk_result(
                risk_result
            )

            strategy = self.strategy_builder.build(
                goal=goal,
                options_result=options_result,
                risk_result=risk_result,
                decision_graph=graph,
                research_context=resolved_research,
            )
            session.set_strategy(strategy)
            session.load_strategy_phases()

            if approved is not None:
                session.approve(
                    approved=approved,
                )

            execution_result: dict[str, Any] = {}

            if auto_execute:
                execution_result = self.execute_session(
                    session_id=session.session_id,
                    approved=approved,
                )

            result = {
                "success": strategy.get(
                    "status"
                ) not in {
                    "BLOCKED",
                    "REJECTED",
                },
                "status": session.status,
                "session_id": session.session_id,
                "goal": goal,
                "decision_graph": graph,
                "options_result": options_result,
                "risk_result": risk_result,
                "strategy": strategy,
                "research_context": resolved_research,
                "execution_result": execution_result,
                "requires_confirmation": strategy.get(
                    "requires_confirmation",
                    False,
                ),
                "requires_research": strategy.get(
                    "requires_research",
                    False,
                ),
                "requires_developer": strategy.get(
                    "requires_developer",
                    False,
                ),
                "allows_automatic_execution": strategy.get(
                    "allows_automatic_execution",
                    False,
                ),
                "blocking_reasons": strategy.get(
                    "blocking_reasons",
                    [],
                ),
                "summary": session.summary(),
            }

            if not auto_execute:
                session.result = dict(result)

            return result

        except Exception as error:
            message = (
                f"ReasoningController error: "
                f"{type(error).__name__}: {error}"
            )

            session.add_error(message)
            session.complete(
                result={
                    "success": False,
                    "status": "FAILED",
                    "error": message,
                },
                success=False,
            )

            self._remember_session(
                session=session,
                result={
                    "success": False,
                    "status": "FAILED",
                    "error": message,
                },
            )

            return {
                "success": False,
                "status": "FAILED",
                "session_id": session.session_id,
                "error": message,
                "summary": session.summary(),
            }

    def analyze(
        self,
        user_request: str,
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.reason(
            user_request=user_request,
            research_context=research_context,
            project_context=project_context,
            auto_execute=False,
            metadata=metadata,
        )

    def create_session(
        self,
        user_request: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        session = ReasoningSession(
            user_request=user_request,
            metadata=metadata,
        )

        self._sessions[session.session_id] = session

        return session.to_dict()

    def execute_session(
        self,
        session_id: str,
        approved: bool | None = None,
    ) -> dict[str, Any]:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "error": (
                    "Nie znaleziono sesji ReasoningSession."
                ),
                "session_id": session_id,
            }

        strategy = session.strategy

        if not strategy:
            return {
                "success": False,
                "status": "BLOCKED",
                "error": (
                    "Sesja nie posiada gotowej strategii."
                ),
                "session_id": session_id,
            }

        if approved is not None:
            session.approve(
                approved=approved
            )

        if strategy.get(
            "requires_confirmation",
            False,
        ) and session.approved is not True:
            return {
                "success": False,
                "status": (
                    "WAITING_FOR_CONFIRMATION"
                ),
                "session_id": session_id,
                "requires_confirmation": True,
                "strategy": strategy,
            }

        if strategy.get(
            "requires_research",
            False,
        ) and not session.research_context:
            return {
                "success": False,
                "status": "WAITING_FOR_RESEARCH",
                "session_id": session_id,
                "requires_research": True,
                "strategy": strategy,
            }

        if strategy.get(
            "status"
        ) in {
            "BLOCKED",
            "REJECTED",
        }:
            return {
                "success": False,
                "status": strategy.get(
                    "status"
                ),
                "session_id": session_id,
                "blocking_reasons": strategy.get(
                    "blocking_reasons",
                    [],
                ),
            }

        if not strategy.get(
            "requires_developer",
            False,
        ):
            result = {
                "success": True,
                "status": "COMPLETED",
                "message": (
                    "Strategia nie wymaga zmian w kodzie."
                ),
                "session_id": session_id,
            }

            session.complete(
                result=result,
                success=True,
            )

            self._remember_session(
                session=session,
                result=result,
            )

            return result

        if self.developer_controller is None:
            result = {
                "success": False,
                "status": "BLOCKED",
                "error": (
                    "DeveloperController nie został "
                    "podłączony do ReasoningController."
                ),
                "session_id": session_id,
            }

            session.complete(
                result=result,
                success=False,
            )

            self._remember_session(
                session=session,
                result=result,
            )

            return result

        session.status = "EXECUTING"

        try:
            developer_result = self._execute_developer(
                session
            )

            session.set_execution(
                developer_result
            )

            validation = self._extract_validation(
                developer_result
            )

            if validation:
                session.set_validation(
                    validation
                )

            rollback = self._extract_rollback(
                developer_result
            )

            if rollback:
                session.set_rollback(
                    rollback
                )

            success = self._detect_success(
                developer_result
            )

            session.complete(
                result=developer_result,
                success=success,
            )

            self._remember_session(
                session=session,
                result=developer_result,
            )

            return {
                "success": bool(success),
                "status": session.status,
                "session_id": session_id,
                "developer_result": developer_result,
                "summary": session.summary(),
            }

        except Exception as error:
            message = (
                f"Developer execution error: "
                f"{type(error).__name__}: {error}"
            )

            result = {
                "success": False,
                "status": "FAILED",
                "error": message,
                "session_id": session_id,
            }

            session.add_error(message)
            session.complete(
                result=result,
                success=False,
            )

            self._remember_session(
                session=session,
                result=result,
            )

            return result

    def approve_session(
        self,
        session_id: str,
        approved: bool,
        note: str | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
            }

        approval = session.approve(
            approved=approved,
            note=note,
        )

        if (
            approved
            and execute
        ):
            return self.execute_session(
                session_id=session_id,
                approved=True,
            )

        return {
            "success": True,
            "session_id": session_id,
            "approval": approval,
            "summary": session.summary(),
        }

    def attach_research(
        self,
        session_id: str,
        research_context: dict[str, Any],
    ) -> dict[str, Any]:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
            }

        context = session.set_research_context(
            research_context
        )

        return {
            "success": True,
            "session_id": session_id,
            "research_context": context,
            "summary": session.summary(),
        }

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            return None

        return session.to_dict()

    def get_session_summary(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            return None

        return session.summary()

    def list_sessions(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:

        normalized_limit = max(
            1,
            int(limit),
        )

        sessions = list(
            self._sessions.values()
        )

        sessions.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return [
            session.summary()
            for session in sessions[
                :normalized_limit
            ]
        ]

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.reasoning_memory.summary()

    def find_similar_history(
        self,
        goal: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        return self.reasoning_memory.find_similar(
            goal=goal,
            limit=limit,
        )

    def _resolve_research_context(
        self,
        goal: dict[str, Any],
        user_request: str,
        research_context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if isinstance(
            research_context,
            dict,
        ) and research_context:
            return dict(research_context)

        if not goal.get(
            "requires_research",
            False,
        ):
            return {}

        if self.research_service is None:
            return {}

        try:
            if hasattr(
                self.research_service,
                "execute",
            ):
                result = self.research_service.execute(
                    user_request
                )

            elif hasattr(
                self.research_service,
                "run",
            ):
                result = self.research_service.run(
                    user_request
                )

            elif hasattr(
                self.research_service,
                "research",
            ):
                result = self.research_service.research(
                    user_request
                )

            elif callable(
                self.research_service
            ):
                result = self.research_service(
                    user_request
                )

            else:
                return {}

            if isinstance(result, dict):
                return result

            return {
                "result": result
            }

        except Exception as error:
            return {
                "success": False,
                "error": (
                    f"ResearchService error: "
                    f"{type(error).__name__}: {error}"
                ),
            }

    def _execute_developer(
        self,
        session: ReasoningSession,
    ) -> dict[str, Any]:

        strategy = session.strategy
        goal = session.goal

        payload = {
            "goal": goal,
            "strategy": strategy,
            "research_context": (
                session.research_context
            ),
            "session_id": session.session_id,
        }

        controller = self.developer_controller

        if hasattr(
            controller,
            "execute_strategy",
        ):
            result = controller.execute_strategy(
                payload
            )

        elif hasattr(
            controller,
            "execute",
        ):
            result = controller.execute(
                payload
            )

        elif hasattr(
            controller,
            "run",
        ):
            result = controller.run(
                payload
            )

        elif hasattr(
            controller,
            "process",
        ):
            result = controller.process(
                payload
            )

        elif callable(controller):
            result = controller(payload)

        else:
            raise TypeError(
                "DeveloperController nie posiada "
                "obsługiwanej metody wykonania."
            )

        if isinstance(result, dict):
            return result

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _extract_validation(
        self,
        developer_result: dict[str, Any],
    ) -> dict[str, Any]:

        for key in [
            "validation",
            "validation_result",
            "validator_result",
        ]:
            value = developer_result.get(key)

            if isinstance(value, dict):
                return dict(value)

        return {}

    def _extract_rollback(
        self,
        developer_result: dict[str, Any],
    ) -> dict[str, Any]:

        for key in [
            "rollback",
            "rollback_result",
        ]:
            value = developer_result.get(key)

            if isinstance(value, dict):
                return dict(value)

        return {}

    def _detect_success(
        self,
        result: dict[str, Any],
    ) -> bool:

        for key in [
            "success",
            "valid",
            "passed",
        ]:
            value = result.get(key)

            if isinstance(value, bool):
                return value

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        if status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "VALIDATED",
        }:
            return True

        if status in {
            "FAILED",
            "ERROR",
            "REJECTED",
            "ROLLED_BACK",
            "BLOCKED",
        }:
            return False

        validation = self._extract_validation(
            result
        )

        if validation:
            for key in [
                "success",
                "valid",
                "passed",
            ]:
                value = validation.get(key)

                if isinstance(value, bool):
                    return value

        return False

    def _remember_session(
        self,
        session: ReasoningSession,
        result: dict[str, Any],
    ) -> None:

        try:
            session_data = session.to_dict()

            goal = session_data.get(
                "goal",
                {}
            )

            metadata = session_data.setdefault(
                "metadata",
                {},
            )

            metadata["detected_modules"] = (
                goal.get(
                    "detected_modules",
                    [],
                )
            )

            metadata["keywords"] = goal.get(
                "keywords",
                [],
            )

            self.reasoning_memory.remember(
                session=session_data,
                result=result,
            )

        except Exception as error:
            session.add_error(
                "ReasoningMemory error: "
                f"{type(error).__name__}: {error}"
            )
