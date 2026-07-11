from __future__ import annotations

import threading
import time
from typing import Any

from app.autodev.background_worker import BackgroundWorker


class BackgroundAutonomyService:

    def __init__(
        self,
        worker: BackgroundWorker | None = None,
    ) -> None:
        self.worker = worker or BackgroundWorker()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return {
                    "success": True,
                    "status": "ALREADY_RUNNING",
                }

            self.worker.enable()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-background-autodev",
                daemon=True,
            )
            self._thread.start()

            return {
                "success": True,
                "status": "STARTED",
            }

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        worker_result = self.worker.disable()

        return {
            "success": True,
            "status": "STOP_REQUESTED",
            "worker": worker_result,
        }

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "RUNNING" if self.is_running() else "STOPPED",
            "running": self.is_running(),
            "worker": self.worker.status(),
        }

    def tick(self) -> dict[str, Any]:
        return self.worker.tick()

    def user_activity(self) -> dict[str, Any]:
        return self.worker.on_user_activity()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.worker.tick()

            interval = self.worker.policy.check_interval_seconds
            self._stop_event.wait(timeout=interval)
from __future__ import annotations

from typing import Any

from app.autodev.autonomous_policy import BackgroundAutonomyPolicy
from app.autodev.autonomous_service import AutonomousService
from app.autodev.autonomous_triggers import AutonomousTriggers
from app.autodev.background_events import BackgroundEventLog


class BackgroundWorker:

    def __init__(
        self,
        *,
        service: AutonomousService | None = None,
        policy: BackgroundAutonomyPolicy | None = None,
        triggers: AutonomousTriggers | None = None,
        events: BackgroundEventLog | None = None,
    ) -> None:
        self.service = service or AutonomousService()
        self.policy = policy or BackgroundAutonomyPolicy()
        self.policy.validate()

        self.triggers = triggers or AutonomousTriggers(
            policy=self.policy
        )
        self.events = events or BackgroundEventLog()

        self.enabled = False
        self.last_evaluation: dict[str, Any] | None = None

    def enable(self) -> dict[str, Any]:
        self.enabled = True
        self.events.add(
            "ENABLED",
            "Background AutoDev został włączony.",
        )
        return {
            "success": True,
            "status": "ENABLED",
        }

    def disable(self) -> dict[str, Any]:
        self.enabled = False
        stop_result = self.service.stop()
        self.events.add(
            "DISABLED",
            "Background AutoDev został wyłączony.",
        )
        return {
            "success": True,
            "status": "DISABLED",
            "stop": stop_result,
        }

    def tick(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "success": True,
                "status": "DISABLED",
            }

        if self.service.is_running():
            return {
                "success": True,
                "status": "ALREADY_RUNNING",
            }

        evaluation = self.triggers.evaluate()
        self.last_evaluation = dict(evaluation)

        if not evaluation["allowed"]:
            self.events.add(
                "SKIPPED",
                "Warunki uruchomienia AutoDev nie zostały spełnione.",
                evaluation,
            )
            return {
                "success": True,
                "status": "SKIPPED",
                "evaluation": evaluation,
            }

        result = self.service.start(
            max_cycles=self.policy.max_cycles_per_run,
            context={
                "background": True,
                "safe_execution": True,
                "auto_rollback": True,
                **dict(context or {}),
            },
            background=self.policy.background_enabled,
        )

        self.events.add(
            "START_ATTEMPT",
            "Podjęto próbę uruchomienia AutoDev w tle.",
            result,
        )

        return result

    def on_user_activity(self) -> dict[str, Any]:
        if (
            self.policy.stop_on_user_activity
            and self.service.is_running()
        ):
            result = self.service.stop()
            self.events.add(
                "STOP_USER_ACTIVITY",
                "AutoDev zatrzymany po wykryciu aktywności użytkownika.",
                result,
            )
            return result

        return {
            "success": True,
            "status": "NO_ACTION",
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "ENABLED" if self.enabled else "DISABLED",
            "enabled": self.enabled,
            "policy": self.policy.to_dict(),
            "service": self.service.status(),
            "last_evaluation": self.last_evaluation,
            "events": self.events.summary(),
        }
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BackgroundEvent:
    event_type: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "message": self.message,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class BackgroundEventLog:

    def __init__(self, max_events: int = 500) -> None:
        self.max_events = max(1, int(max_events))
        self.events: list[BackgroundEvent] = []

    def add(
        self,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> BackgroundEvent:
        event = BackgroundEvent(
            event_type=str(event_type),
            message=str(message),
            metadata=dict(metadata or {}),
        )
        self.events.append(event)

        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        return event

    def last(self) -> BackgroundEvent | None:
        return self.events[-1] if self.events else None

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.events),
            "last": self.last().to_dict() if self.last() else None,
        }
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class BackgroundAutonomyPolicy:
    enabled: bool = True
    idle_seconds_required: float = 300.0
    max_cpu_percent: float = 65.0
    max_cycles_per_run: int = 2
    check_interval_seconds: float = 5.0
    stop_on_user_activity: bool = True
    background_enabled: bool = True

    def validate(self) -> None:
        if self.idle_seconds_required < 0:
            raise ValueError(
                "idle_seconds_required nie może być ujemne."
            )
        if not 0 <= self.max_cpu_percent <= 100:
            raise ValueError(
                "max_cpu_percent musi być w zakresie 0-100."
            )
        if self.max_cycles_per_run < 1:
            raise ValueError(
                "max_cycles_per_run musi być większe od 0."
            )
        if self.check_interval_seconds <= 0:
            raise ValueError(
                "check_interval_seconds musi być większe od 0."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
from __future__ import annotations

from typing import Any, Callable

from app.autodev.autonomous_policy import BackgroundAutonomyPolicy
from app.autodev.idle_detector import IdleDetector


class AutonomousTriggers:

    def __init__(
        self,
        *,
        policy: BackgroundAutonomyPolicy,
        idle_detector: IdleDetector | None = None,
        cpu_provider: Callable[[], float] | None = None,
    ) -> None:
        self.policy = policy
        self.idle_detector = idle_detector or IdleDetector()
        self.cpu_provider = cpu_provider or (lambda: 0.0)

    def evaluate(self) -> dict[str, Any]:
        idle_seconds = self.idle_detector.idle_seconds()
        cpu_percent = max(0.0, float(self.cpu_provider()))

        reasons: list[str] = []

        if not self.policy.enabled:
            reasons.append("Autonomia tła jest wyłączona.")

        if idle_seconds < self.policy.idle_seconds_required:
            reasons.append("Użytkownik nie jest wystarczająco długo bezczynny.")

        if cpu_percent > self.policy.max_cpu_percent:
            reasons.append("Użycie CPU jest zbyt wysokie.")

        return {
            "allowed": not reasons,
            "idle_seconds": idle_seconds,
            "cpu_percent": cpu_percent,
            "reasons": reasons,
        }
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class IdleDetector:

    def __init__(
        self,
        provider: Callable[[], float] | None = None,
    ) -> None:
        self.provider = provider

    def idle_seconds(self) -> float:
        if self.provider is not None:
            return max(0.0, float(self.provider()))

        try:
            info = _LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(_LASTINPUTINFO)

            if not ctypes.windll.user32.GetLastInputInfo(
                ctypes.byref(info)
            ):
                return 0.0

            tick_count = ctypes.windll.kernel32.GetTickCount()
            elapsed_ms = int(tick_count) - int(info.dwTime)

            return max(0.0, elapsed_ms / 1000.0)

        except Exception:
            return 0.0

    def is_idle(self, required_seconds: float) -> bool:
        return self.idle_seconds() >= max(
            0.0,
            float(required_seconds),
        )
from __future__ import annotations

from typing import Any

from app.autodev.background_service import BackgroundAutonomyService


class BackgroundCommands:

    PREFIXES = (
        "background autodev ",
        "autodev background ",
        "auto rozwój w tle ",
        "auto rozwoj w tle ",
    )

    def __init__(
        self,
        service: BackgroundAutonomyService | None = None,
    ) -> None:
        self.service = service or BackgroundAutonomyService()

    def can_handle(self, command: str) -> bool:
        normalized = str(command).strip().casefold()
        return normalized.startswith(self.PREFIXES)

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(command).strip().casefold()

        if " start" in normalized or " uruchom" in normalized:
            return self.service.start()

        if " stop" in normalized or " zatrzymaj" in normalized:
            return self.service.stop()

        if " status" in normalized or " stan" in normalized:
            return self.service.status()

        if " tick" in normalized or " sprawdź" in normalized or " sprawdz" in normalized:
            return self.service.tick()

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": command,
        }
from __future__ import annotations

from typing import Any

from app.autodev.experience_memory import ExperienceMemory


class LearningEngine:

    def __init__(
        self,
        memory: ExperienceMemory | None = None,
    ) -> None:
        self.memory = memory or ExperienceMemory()

    def learn_from_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(result or {})
        generation = result.get("generation")
        if not isinstance(generation, dict):
            generation = {}

        execution = result.get("execution")
        if not isinstance(execution, dict):
            execution = {}

        task = generation.get("task")
        if not isinstance(task, dict):
            task = {}

        source = execution or generation or result

        record = self.memory.remember(
            success=bool(source.get("success", result.get("success", False))),
            status=str(source.get("status", result.get("status", "UNKNOWN"))),
            goal=str(
                task.get(
                    "description",
                    task.get("title", generation.get("goal", "")),
                )
            ),
            task_id=str(task.get("task_id", generation.get("planner_task_id", ""))),
            target=str(task.get("target", "")),
            errors=list(source.get("errors") or []),
            lessons=[
                str(source.get("message"))
            ] if source.get("message") else [],
            metadata={
                "runtime_status": str(result.get("status", "")),
            },
        )

        return {
            "success": True,
            "status": "LEARNED",
            "record": record.to_dict(),
            "memory": self.memory.summary(),
        }

    def summary(self) -> dict[str, Any]:
        return self.memory.summary()
