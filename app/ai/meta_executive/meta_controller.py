from __future__ import annotations

from app.core.project_paths import default_project_root

from typing import Any

from app.ai.meta_executive.meta_engine import (
    MetaEngine,
)
from app.ai.meta_executive.meta_memory import (
    MetaMemory,
)
from app.ai.meta_executive.meta_planner import (
    MetaPlanner,
)


class MetaController:

    def __init__(
        self,
        project_root: str | None = None,
        meta_engine: MetaEngine | None = None,
        meta_memory: MetaMemory | None = None,
        meta_planner: MetaPlanner | None = None,
        executive_controller: Any | None = None,
        project_director: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
        reasoning_service: Any | None = None,
        research_service: Any | None = None,
        autonomous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "MetaController wymaga project_root."
            )

        self.meta_memory = (
            meta_memory
            if meta_memory is not None
            else MetaMemory()
        )

        self.meta_planner = (
            meta_planner
            if meta_planner is not None
            else MetaPlanner()
        )

        self.autonomous_dev_controller = autonomous_dev_controller

        self.meta_engine = (
            meta_engine
            if meta_engine is not None
            else MetaEngine(
                project_root=self.project_root,
                planner=self.meta_planner,
                memory=self.meta_memory,
                executive_controller=executive_controller,
                project_director=project_director,
                improvement_controller=(
                    improvement_controller
                ),
                evolution_controller=(
                    evolution_controller
                ),
                continuous_dev_controller=(
                    continuous_dev_controller
                ),
                reasoning_service=reasoning_service,
                research_service=research_service,
            )
        )

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_cycles: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.meta_engine.create_session(
            objective=objective,
            mode=mode,
            max_cycles=max_cycles,
            context=context,
            metadata=metadata,
        )

    def start_session(
        self,
        meta_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.meta_engine.start(
            meta_id=meta_id,
            approved=approved,
            context=context,
        )

    def create_and_start(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_cycles: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        approved: bool | None = None,
    ) -> dict[str, Any]:

        created = self.create_session(
            objective=objective,
            mode=mode,
            max_cycles=max_cycles,
            context=context,
            metadata=metadata,
        )

        meta_id = str(
            created.get(
                "meta_id",
                "",
            )
        ).strip()

        if not meta_id:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "MetaController nie otrzymał meta_id."
                ),
            }

        result = self.start_session(
            meta_id=meta_id,
            approved=approved,
            context=context,
        )

        if mode == "AUTONOMOUS" and result.get("success", False):
            result=dict(result)
            result["autodev"]=self._delegate_to_autodev(objective, context)

        return result

    def approve_session(
        self,
        meta_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.meta_engine.approve(
            meta_id=meta_id,
            approved=approved,
            context=context,
        )

    def get_session(
        self,
        meta_id: str,
    ) -> dict[str, Any] | None:

        return self.meta_engine.get_session(
            meta_id
        )

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.meta_engine.list_sessions(
            limit=limit
        )

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.meta_memory.summary()

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "engine": self.meta_engine.summary(),
            "memory": self.meta_memory.summary(),
            "project_root": self.project_root,
            "controller_version": "1.0.0",
        }

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_command = str(
            command
        ).strip()

        if not normalized_command:
            return {
                "success": False,
                "status": "EMPTY_COMMAND",
                "error": (
                    "Polecenie Meta Executive jest puste."
                ),
            }

        lowered = normalized_command.lower()
        normalized_context = self._safe_dict(
            context
        )

        start_prefixes = (
            "meta executive start ",
            "meta start ",
            "ceo meta start ",
            "nadrzędny zarząd start ",
            "nadrzedny zarzad start ",
        )

        for prefix in start_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_and_start(
                    objective=objective,
                    mode="SAFE_AUTONOMOUS",
                    context=normalized_context,
                )

        autonomous_prefixes = (
            "meta executive autonomous ",
            "meta autonomous ",
            "ceo meta autonomous ",
            "nadrzędny zarząd autonomicznie ",
            "nadrzedny zarzad autonomicznie ",
        )

        for prefix in autonomous_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_and_start(
                    objective=objective,
                    mode="AUTONOMOUS",
                    context=normalized_context,
                    approved=True,
                )

        create_prefixes = (
            "meta executive create ",
            "meta create ",
            "ceo meta create ",
            "nadrzędny zarząd utwórz ",
            "nadrzedny zarzad utworz ",
        )

        for prefix in create_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_session(
                    objective=objective,
                    context=normalized_context,
                )

        approve_prefixes = (
            "meta executive approve ",
            "meta approve ",
            "ceo meta approve ",
            "nadrzędny zarząd zaakceptuj ",
            "nadrzedny zarzad zaakceptuj ",
        )

        for prefix in approve_prefixes:
            if lowered.startswith(
                prefix
            ):
                meta_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    meta_id=meta_id,
                    approved=True,
                    context=normalized_context,
                )

        reject_prefixes = (
            "meta executive reject ",
            "meta reject ",
            "ceo meta reject ",
            "nadrzędny zarząd odrzuć ",
            "nadrzedny zarzad odrzuc ",
        )

        for prefix in reject_prefixes:
            if lowered.startswith(
                prefix
            ):
                meta_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    meta_id=meta_id,
                    approved=False,
                    context=normalized_context,
                )

        status_prefixes = (
            "meta executive status ",
            "meta status ",
            "ceo meta status ",
            "nadrzędny zarząd status ",
            "nadrzedny zarzad status ",
        )

        for prefix in status_prefixes:
            if lowered.startswith(
                prefix
            ):
                meta_id = normalized_command[
                    len(prefix):
                ].strip()

                session = self.get_session(
                    meta_id
                )

                if session is None:
                    return {
                        "success": False,
                        "status": "NOT_FOUND",
                        "meta_id": meta_id,
                    }

                return {
                    "success": True,
                    "status": "FOUND",
                    "meta_id": meta_id,
                    "session": session,
                }

        if lowered in {
            "meta executive list",
            "meta list",
            "ceo meta list",
            "nadrzędny zarząd lista",
            "nadrzedny zarzad lista",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "sessions": self.list_sessions(),
            }

        if lowered in {
            "meta executive summary",
            "meta summary",
            "ceo meta summary",
            "nadrzędny zarząd podsumowanie",
            "nadrzedny zarzad podsumowanie",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "summary": self.system_summary(),
            }

        if lowered in {
            "meta executive memory",
            "meta memory",
            "ceo meta memory",
            "nadrzędny zarząd pamięć",
            "nadrzedny zarzad pamiec",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": self.memory_summary(),
            }

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": normalized_command,
            "error": (
                "Nie rozpoznano polecenia Meta Executive."
            ),
        }

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(
            command
        ).strip().lower()

        prefixes = (
            "meta executive ",
            "meta ",
            "ceo meta ",
            "nadrzędny zarząd ",
            "nadrzedny zarzad ",
        )

        return normalized.startswith(
            prefixes
        )


    def _delegate_to_autodev(
        self,
        objective:str,
        context:dict[str,Any]|None=None,
    )->dict[str,Any]:
        c=self.autonomous_dev_controller
        if c is None:
            return {"success":False,"status":"AUTODEV_UNAVAILABLE"}
        h=getattr(c,"handle",None)
        if callable(h):
            try:
                r=h(command=objective,context=context)
            except TypeError:
                r=h(objective)
            return r if isinstance(r,dict) else {"success":True,"status":"COMPLETED","result":r}
        return {"success":False,"status":"AUTODEV_INVALID"}

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
