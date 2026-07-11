from __future__ import annotations

from typing import Any

from app.ai.reasoner.reasoner_router import ReasonerRoute
from app.ai.reasoner.reasoner_router import ReasonerRouter
from app.ai.reasoner.reasoning_controller import ReasoningController


class ReasoningService:

    def __init__(
        self,
        router: ReasonerRouter | None = None,
        controller: ReasoningController | None = None,
    ) -> None:

        self.router = (
            router
            if router is not None
            else ReasonerRouter()
        )

        self.controller = (
            controller
            if controller is not None
            else ReasoningController()
        )

    def can_handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> bool:

        route_result = self.router.route(
            command=command,
            context=context,
        )

        return bool(
            route_result.get(
                "matched",
                False,
            )
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_context = (
            dict(context)
            if isinstance(context, dict)
            else {}
        )

        route_result = self.router.route(
            command=command,
            context=normalized_context,
        )

        if not route_result.get(
            "matched",
            False,
        ):
            return {
                "handled": False,
                "success": False,
                "route": ReasonerRoute.NONE.value,
                "status": "NOT_MATCHED",
                "command": command,
                "route_result": route_result,
            }

        route = str(
            route_result.get(
                "route",
                ReasonerRoute.NONE.value,
            )
        ).upper()

        payload = route_result.get(
            "payload",
            {},
        )

        if not isinstance(payload, dict):
            payload = {}

        try:
            result = self._dispatch(
                route=route,
                payload=payload,
                context=normalized_context,
            )

            return {
                "handled": True,
                "success": self._detect_success(
                    result
                ),
                "route": route,
                "status": self._extract_status(
                    result
                ),
                "command": command,
                "result": result,
                "route_result": route_result,
            }

        except Exception as error:
            return {
                "handled": True,
                "success": False,
                "route": route,
                "status": "FAILED",
                "command": command,
                "error": (
                    f"ReasoningService error: "
                    f"{type(error).__name__}: {error}"
                ),
                "route_result": route_result,
            }

    def process(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.handle(
            command=command,
            context=context,
        )

    def execute(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.handle(
            command=command,
            context=context,
        )

    def reason(
        self,
        user_request: str,
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
        auto_execute: bool = False,
        approved: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.controller.reason(
            user_request=user_request,
            research_context=research_context,
            project_context=project_context,
            auto_execute=auto_execute,
            approved=approved,
            metadata=metadata,
        )

    def analyze(
        self,
        user_request: str,
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.controller.analyze(
            user_request=user_request,
            research_context=research_context,
            project_context=project_context,
            metadata=metadata,
        )

    def _dispatch(
        self,
        route: str,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        if route == ReasonerRoute.REASON.value:
            return self.controller.reason(
                user_request=str(
                    payload.get(
                        "user_request",
                        payload.get(
                            "command",
                            "",
                        ),
                    )
                ),
                research_context=self._safe_dict_or_none(
                    payload.get(
                        "research_context"
                    )
                ),
                project_context=self._safe_dict_or_none(
                    payload.get(
                        "project_context"
                    )
                ),
                auto_execute=bool(
                    payload.get(
                        "auto_execute",
                        False,
                    )
                ),
                approved=self._optional_bool(
                    payload.get(
                        "approved"
                    )
                ),
                metadata=self._build_metadata(
                    route=route,
                    payload=payload,
                    context=context,
                ),
            )

        if route == ReasonerRoute.ANALYZE.value:
            return self.controller.analyze(
                user_request=str(
                    payload.get(
                        "user_request",
                        payload.get(
                            "command",
                            "",
                        ),
                    )
                ),
                research_context=self._safe_dict_or_none(
                    payload.get(
                        "research_context"
                    )
                ),
                project_context=self._safe_dict_or_none(
                    payload.get(
                        "project_context"
                    )
                ),
                metadata=self._build_metadata(
                    route=route,
                    payload=payload,
                    context=context,
                ),
            )

        if route == ReasonerRoute.EXECUTE.value:
            session_id = self._require_session_id(
                payload
            )

            return self.controller.execute_session(
                session_id=session_id,
                approved=self._optional_bool(
                    payload.get(
                        "approved"
                    )
                ),
            )

        if route == ReasonerRoute.APPROVE.value:
            session_id = self._require_session_id(
                payload
            )

            return self.controller.approve_session(
                session_id=session_id,
                approved=bool(
                    payload.get(
                        "approved",
                        True,
                    )
                ),
                note=self._optional_string(
                    payload.get(
                        "note"
                    )
                ),
                execute=bool(
                    payload.get(
                        "execute",
                        False,
                    )
                ),
            )

        if route == ReasonerRoute.ATTACH_RESEARCH.value:
            session_id = self._require_session_id(
                payload
            )

            research_context = payload.get(
                "research_context",
                {},
            )

            if not isinstance(
                research_context,
                dict,
            ):
                raise TypeError(
                    "ResearchContext musi być typu dict."
                )

            return self.controller.attach_research(
                session_id=session_id,
                research_context=research_context,
            )

        if route == ReasonerRoute.SESSION_STATUS.value:
            session_id = self._require_session_id(
                payload
            )

            session = self.controller.get_session(
                session_id
            )

            if session is None:
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "session_id": session_id,
                }

            summary = self.controller.get_session_summary(
                session_id
            )

            return {
                "success": True,
                "status": "FOUND",
                "session_id": session_id,
                "session": session,
                "summary": summary,
            }

        if route == ReasonerRoute.MEMORY_SUMMARY.value:
            return {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": (
                    self.controller.memory_summary()
                ),
            }

        if route == ReasonerRoute.FIND_SIMILAR.value:
            goal = payload.get(
                "goal",
                {},
            )

            if not isinstance(goal, dict):
                raise TypeError(
                    "Goal dla FIND_SIMILAR musi być dict."
                )

            limit = self._safe_int(
                payload.get(
                    "limit",
                    5,
                ),
                5,
            )

            return {
                "success": True,
                "status": "COMPLETED",
                "matches": (
                    self.controller.find_similar_history(
                        goal=goal,
                        limit=limit,
                    )
                ),
            }

        return {
            "success": False,
            "status": "UNSUPPORTED_ROUTE",
            "route": route,
        }

    def _build_metadata(
        self,
        route: str,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        metadata = {
            "source": "ReasoningService",
            "route": route,
            "service_version": "1.0.0",
        }

        context_metadata = context.get(
            "metadata"
        )

        if isinstance(
            context_metadata,
            dict,
        ):
            metadata.update(
                context_metadata
            )

        payload_context = payload.get(
            "context"
        )

        if isinstance(
            payload_context,
            dict,
        ):
            nested_metadata = payload_context.get(
                "metadata"
            )

            if isinstance(
                nested_metadata,
                dict,
            ):
                metadata.update(
                    nested_metadata
                )

        return metadata

    def _require_session_id(
        self,
        payload: dict[str, Any],
    ) -> str:

        session_id = self._optional_string(
            payload.get(
                "session_id"
            )
        )

        if session_id is None:
            raise ValueError(
                "Brak session_id dla operacji Reasonera."
            )

        return session_id

    def _extract_status(
        self,
        result: Any,
    ) -> str:

        if isinstance(result, dict):
            return str(
                result.get(
                    "status",
                    (
                        "COMPLETED"
                        if result.get(
                            "success"
                        ) is True
                        else "UNKNOWN"
                    ),
                )
            )

        return "COMPLETED"

    def _detect_success(
        self,
        result: Any,
    ) -> bool:

        if not isinstance(result, dict):
            return True

        value = result.get(
            "success"
        )

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
            "FOUND",
            "READY",
            "READY_FOR_EXECUTION",
            "WAITING_FOR_CONFIRMATION",
            "WAITING_FOR_RESEARCH",
        }:
            return True

        if status in {
            "FAILED",
            "ERROR",
            "REJECTED",
            "BLOCKED",
            "NOT_FOUND",
            "UNSUPPORTED_ROUTE",
        }:
            return False

        return True

    def _optional_bool(
        self,
        value: Any,
    ) -> bool | None:

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

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

    def _safe_dict_or_none(
        self,
        value: Any,
    ) -> dict[str, Any] | None:

        if isinstance(value, dict):
            return dict(value)

        return None

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
