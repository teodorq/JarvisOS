"""Lazy construction for optional assistant suites used after startup."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.core.project_paths import resolve_project_root


DEFERRED_STAGES = {
    "B101": "VISION_3_READY",
    "B102": "BRAIN_2_READY",
    "B103": "DESKTOP_AGENT_2_READY",
    "B104": "MEMORY_2_READY",
    "B105": "AUTONOMY_CONTROL_CENTER_2_READY",
    "B106": "LOCAL_MAIL_CENTER_READY",
    "B107": "LOCAL_CALENDAR_READY",
    "B108": "LOCAL_DOCUMENT_CENTER_READY",
    "B109": "REMINDER_CENTER_2_READY",
    "B110": "DAILY_PRODUCTIVITY_REPORTING_READY",
    "B111": "REAL_SCENARIO_VALIDATION_READY",
    "B112": "RUNTIME_PERFORMANCE_READY",
    "B113": "RUNTIME_RECOVERY_READY",
    "B114": "SAFE_SERVICE_RESTART_READY",
    "B115": "BUSINESS_BETA_READINESS_READY",
    "B121": "NATURAL_CONVERSATION_3_READY",
    "B122": "UNIFIED_CONTEXT_HUB_READY",
    "B123": "UNIFIED_PRODUCTIVITY_ROUTER_READY",
    "B124": "ASSISTANT_PROGRESS_RUNTIME_READY",
    "B125": "BUSINESS_1_2_BETA_READINESS_READY",
    "B126": "REAL_GMAIL_CENTER_READY",
    "B127": "REAL_GOOGLE_CALENDAR_READY",
    "B128": "REAL_GOOGLE_DRIVE_READY",
    "B129": "ONLINE_DAY_CENTER_READY",
    "B130": "BUSINESS_1_2_STABLE_RC_READINESS_READY",
    "B131": "WORKSPACE_RELIABILITY_READY",
    "B132": "GMAIL_WORKFLOWS_READY",
    "B133": "CALENDAR_INTELLIGENCE_READY",
    "B134": "DRIVE_DOCUMENTS_READY",
    "B135": "ONLINE_ASSISTANT_1_3_BETA_READINESS_READY",
    "B141": "NATURAL_INTENT_UNDERSTANDING_READY",
    "B142": "UNIVERSAL_SLOT_EXTRACTION_READY",
    "B143": "GOOGLE_PRODUCTIVITY_ACTIONS_READY",
    "B144": "MULTI_TURN_CLARIFICATION_READY",
    "B145": "SURPRISE_GENERALIZATION_GATES_READY",
    "B146": "CONVERSATION_ACTION_MEMORY_READY",
    "B147": "CONTACT_RESOLUTION_AND_VALIDATION_READY",
    "B148": "NATURAL_CORRECTION_FLOW_READY",
    "B149": "ONE_INTENT_ONE_EXECUTION_READY",
    "B150": "PRACTICAL_SURPRISE_SUITE_READY",
    "B151": "CALENDAR_EVENT_MUTATION_READY",
    "B152": "CALENDAR_EVENT_SEARCH_READY",
    "B153": "CONFIRMED_EXISTING_DRAFT_SEND_READY",
    "B154": "CONTACT_ALIAS_CONTINUITY_READY",
    "B155": "DAILY_ACTION_SURPRISE_GATES_READY",
    "B156": "INTELLIGENT_DAY_OVERVIEW_READY",
    "B157": "TODAY_REACTION_PRIORITY_READY",
    "B158": "NATURAL_DAY_PLANNING_READY",
    "B159": "COMPLETION_MEMORY_READY",
    "B160": "DAILY_USEFULNESS_GATES_READY",
    "B161": "AUTOMATIC_DAILY_BRIEF_READY",
    "B162": "URGENT_SIGNAL_AND_CONFLICT_DETECTION_READY",
    "B163": "SELECTIVE_NOTIFICATION_POLICY_READY",
    "B164": "NEXT_BEST_ACTION_PROPOSALS_READY",
    "B165": "PROACTIVE_DAILY_USEFULNESS_GATES_READY",
    "B166": "ACTIVE_ISSUE_ADVICE_READY",
    "B167": "CONFIRMED_CONFLICT_RESOLUTION_READY",
    "B168": "IMPORTANT_MAIL_REPLY_DRAFT_READY",
    "B169": "SNOOZE_IGNORE_COMPLETE_READY",
    "B170": "DETECT_PROPOSE_EXECUTE_VERIFY_READY",
    "B171": "STALE_CALENDAR_PLAN_GUARD_READY",
    "B172": "LIVE_CALENDAR_RESULT_VERIFICATION_READY",
    "B173": "DUPLICATE_PROTECTION_SAFE_RETRY_READY",
    "B174": "SAFE_UNDO_LAST_CALENDAR_CHANGE_READY",
    "B175": "RELIABILITY_RELEASE_GATE_READY",
    "B176": "STARTUP_CONFLICT_SCAN_READY",
    "B177": "NEW_CHANGED_CONFLICT_NOTIFICATION_READY",
    "B178": "LIVE_CONFLICT_REFRESH_READY",
    "B178.1": "LIVE_REFRESH_FALLBACK_SUPPRESSION_READY",
    "B179": "SAFE_PROACTIVITY_POLICY_READY",
    "B180": "PROACTIVE_CALENDAR_RELIABILITY_GATE_READY",
    "B181": "EXACT_ALERT_CONFLICT_CONTEXT_READY",
    "B182": "EXACT_SAFE_CONFLICT_PROPOSAL_READY",
    "B186": "LIVE_GMAIL_SEARCH_READY",
    "B187": "FULL_GMAIL_THREAD_READ_READY",
    "B188": "THREADED_REPLY_DRAFT_READY",
    "B189": "CONFIRMED_VERIFIED_GMAIL_SEND_READY",
    "B190": "GMAIL_LIVE_RELIABILITY_GATE_READY",
    "B190.1": "GMAIL_WORKFLOW_QUALITY_CLOSURE_READY",
    "B190.2": "GMAIL_SEND_CONFIRMATION_BRIDGE_READY",
}


class LazyAssistantService:
    """Thread-safe proxy with deferred progress callback registration."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._instance: Any | None = None
        self._progress_callback: Any | None = None
        self._lock = RLock()

    @property
    def loaded(self) -> bool:
        return self._instance is not None

    def set_progress_callback(self, callback: Any | None) -> None:
        with self._lock:
            self._progress_callback = callback
            instance = self._instance
        if instance is not None:
            instance.set_progress_callback(callback)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._load(), name)

    def _load(self) -> Any:
        with self._lock:
            if self._instance is None:
                instance = self._factory()
                callback = self._progress_callback
                if callback is not None and hasattr(instance, "set_progress_callback"):
                    instance.set_progress_callback(callback)
                self._instance = instance
            return self._instance


class DeferredAssistantServices:
    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        stability_runtime_status: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.intelligence = LazyAssistantService(
            lambda: _intelligence_controller(root)
        )
        self.productivity = LazyAssistantService(
            lambda: _productivity_controller(root)
        )
        self.stability = LazyAssistantService(
            lambda: _stability_controller(root, stability_runtime_status)
        )
        self.assistant_v12 = LazyAssistantService(
            lambda: _assistant_v12_controller(root)
        )
        self.online = LazyAssistantService(
            lambda: _online_controller(root, self.productivity.reminders)
        )
        self.natural_actions = LazyAssistantService(
            lambda: _natural_actions(root, self.online._load())
        )


def _productivity_controller(root: Path) -> Any:
    from app.productivity.controller import ProductivitySuiteController
    return ProductivitySuiteController(root)


def _intelligence_controller(root: Path) -> Any:
    from app.intelligence.controller import IntelligenceSuiteController
    return IntelligenceSuiteController(root)


def _stability_controller(root: Path, runtime_status: Any) -> Any:
    from app.stability.controller import StabilitySuiteController
    return StabilitySuiteController(root, runtime_status=runtime_status)


def _assistant_v12_controller(root: Path) -> Any:
    from app.assistant_v12.controller import AssistantV12Controller
    return AssistantV12Controller(root)


def _online_controller(root: Path, reminders: Any) -> Any:
    from app.online_assistant.controller import OnlineAssistantController
    return OnlineAssistantController(root, reminders=reminders)


def _natural_actions(root: Path, online: Any) -> Any:
    from app.natural_actions import NaturalActionService
    return NaturalActionService(root, online=online)


def deferred_matches(command: object) -> bool:
    from app.intelligence.controller import IntelligenceSuiteController
    if IntelligenceSuiteController.matches(command):
        return True
    from app.stability.controller import StabilitySuiteController
    if StabilitySuiteController.matches(command):
        return True
    from app.assistant_v12.conversation_engine import NaturalConversationEngineV3
    if NaturalConversationEngineV3.matches(command):
        return True
    from app.productivity.controller import ProductivitySuiteController
    if ProductivitySuiteController.matches(command):
        return True
    from app.online_assistant.controller import OnlineAssistantController
    if OnlineAssistantController.matches(command):
        return True
    from app.natural_actions import NaturalActionService
    return NaturalActionService.matches(command)


def google_token_present(environment: dict[str, str] | None = None) -> bool:
    source = os.environ if environment is None else environment
    local = Path(source.get("LOCALAPPDATA", str(Path.home() / ".jarvis_os")))
    return (local / "JARVIS_OS" / "secrets" / "google_workspace_token.json").is_file()


__all__ = [
    "DEFERRED_STAGES", "DeferredAssistantServices", "LazyAssistantService",
    "deferred_matches", "google_token_present",
]
