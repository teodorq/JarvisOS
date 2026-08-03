from __future__ import annotations
from app.ai.actions import ActionTypes
from app.gui.command_safety import (
    is_safe_read_only_thought, is_safe_workspace_preparation_thought,
)
from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.client_speech_state import speak_with_client_state
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.gui.client_command_runtime import ClientCommandRuntimeMixin
from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.gui.owner_background_commands import execute_owner_thought, shutdown_owner_commands, start_owner_command
from app.gui.repeated_confirmation import repeated_calendar_confirmation
class BusinessCommandRuntimeMixin(ClientCommandRuntimeMixin):
    """Voice, confirmation and command execution lifecycle for Business UI."""
    def _on_assistant_v12_progress(self, operation: dict) -> None:
        if not bool(getattr(self, "_interface_ready", True)):
            return
        phase = str(operation.get("phase", "DZIAŁAM"))
        percent = int(operation.get("progress_percent", 0) or 0)
        status = str(operation.get("status", "RUNNING"))
        message = str(operation.get("message", "")).strip()
        if status == "FAILED":
            self.console_page.set_state("BŁĄD ASYSTENTA 1.2", "danger")
        elif status == "COMPLETED":
            self.console_page.set_state("GOTOWY NA POLECENIE", "healthy")
        elif phase == "RETRY":
            self.console_page.set_state(f"RETRY • {percent}%", "danger")
        elif phase in {"ROZUMIENIE", "KONTEKST", "ROUTING"}:
            self.console_page.set_state(f"MYŚLĘ • {percent}%", "accent")
        else:
            self.console_page.set_state(f"DZIAŁAM • {percent}%", "accent")
        if message:
            self.console_page.append(
                f"Jarvis 1.2: {phase} {percent}% — {message}"
            )
    def _background_status(self) -> str:
        try:
            status = self.brain.background_status()
            if status.get("running", False):
                return "RUNNING"
            if status.get("status") == "STOPPED":
                return "READY"
        except Exception:
            controller = getattr(self.brain, "autonomous_dev_controller", None)
            if controller is not None:
                try:
                    status = controller.status()
                    return "RUNNING" if status.get("timed_loop_running") else "READY"
                except Exception:
                    return "OFFLINE"
        return "OFFLINE"
    def _process_typed_command(self, text: str) -> None:
        self.process_command(text, source="Ty")
    def handle_voice_text_safe(self, text: str) -> None:
        self.voice_text_signal.emit(text)
    def handle_voice_text(self, text: str) -> None:
        # [voice_error] and Voice runtime diagnostic: stay outside Brain.
        from app.gui.voice_command_dispatch import dispatch_voice_text
        dispatch_voice_text(self, text)
    def say_safe(self, text: str) -> None: speak_with_client_state(self, text)

    def is_safe_thought(self, thought: dict) -> bool:
        if (
            is_safe_read_only_thought(thought)
            or is_safe_workspace_preparation_thought(thought)
        ):
            return True
        if thought.get("handler") in {
            "background_autodev", "autonomous_autodev", "autodev",
        }:
            return True
        safe_actions = {
            ActionTypes.OPEN_WEBSITE, ActionTypes.OPEN_APP,
            ActionTypes.GOOGLE_SEARCH, ActionTypes.YOUTUBE_SEARCH,
            ActionTypes.TYPE_TEXT, ActionTypes.PRESS_ENTER,
            ActionTypes.CLICK, ActionTypes.SCREENSHOT,
            ActionTypes.VISION_ANALYZE, ActionTypes.VISION_CLICK,
            ActionTypes.YOUTUBE_FIRST_VIDEO, ActionTypes.REMEMBER,
            ActionTypes.ADD_TASK, ActionTypes.MEMORY_SUMMARY,
        }
        actions = thought.get("actions", [])
        return bool(actions) and all(
            action.get("action_type") in safe_actions
            for action in actions if isinstance(action, dict)
        )

    def process_command(self, text: str, source: str = "Ty") -> None:
        self.console_page.append(f"\n{source}: {text}")
        self._show_page("console")
        if self.pending_thought is not None:
            self.handle_confirmation(text)
            return
        repeated = repeated_calendar_confirmation(self, text)
        if repeated is not None:
            self._execute_repeated_calendar_confirmation(text, repeated)
            return
        if text.lower().strip() in {"jarvis", "hej jarvis", "cześć jarvis"}:
            self.console_page.append("Jarvis: Słucham.")
            self.say_safe("Słucham")
            return
        if start_owner_command(self, text): return
        self.console_page.set_state("ANALIZA POLECENIA", "accent")
        priority = active_resolution_priority_thought(self, text)
        thought = priority if priority is not None else self.brain.think(text)
        self.console_page.append("Jarvis: Plan działania:")
        for index, step in enumerate(thought.get("plan", []), start=1):
            self.console_page.append(f"{index}. {step}")
        if not thought.get("can_execute", False):
            self.console_page.append("Jarvis: Nie wykonuję tej akcji.")
            self.console_page.set_state("POLECENIE ODRZUCONE", "danger")
            return
        read_only = (
            is_safe_read_only_thought(thought)
            or is_safe_workspace_preparation_thought(thought)
        )
        authorization = self.business_service.access_control.authorize(
            text,
            read_only=read_only,
        )
        if not authorization.get("allowed", False):
            self.console_page.append(
                "Jarvis: Odmowa uprawnień — "
                + str(authorization.get("reason", "brak uprawnienia"))
            )
            self.console_page.set_state("ODMOWA UPRAWNIEŃ", "danger")
            return
        if self.is_safe_thought(thought):
            self._execute_thought(thought)
            return
        self.pending_thought = thought
        self.console_page.set_state("OCZEKIWANIE NA POTWIERDZENIE", "danger")
        confirmation = str(thought.get("confirmation_message", "")).strip()
        self.console_page.append(
            "Jarvis: " + (confirmation or (
                "Ta akcja może być ważna. Wpisz TAK, żeby wykonać, "
                "albo NIE, żeby anulować."
            ))
        )
        self.say_safe("Potwierdź wykonanie.")


    def _execute_repeated_calendar_confirmation(
        self, command: str, thought: dict
    ) -> None:
        authorization = self.business_service.access_control.authorize(
            command, read_only=False,
        )
        if not authorization.get("allowed", False):
            self.console_page.set_state("ODMOWA UPRAWNIEŃ", "danger")
            self.console_page.append("Jarvis: Nie mam uprawnień do tego działania.")
            return
        self.console_page.set_state("SPRAWDZAM POPRZEDNIĄ ZMIANĘ", "accent")
        self._execute_thought(thought)

    def _execute_thought(self, thought: dict) -> None:
        if execute_owner_thought(self, thought): return
        response = execute_confirmed_calendar_plan(self, thought)
        self.console_page.append(f"Jarvis: {response}")
        self.console_page.set_state("GOTOWY NA POLECENIE", "healthy")
        self.say_safe(response)

    def handle_confirmation(self, answer: str) -> None:
        handle_owner_confirmation(self, answer)

    def closeEvent(self, event) -> None:
        shutdown_owner_commands(self)
        try:
            if self.voice is not None:
                self.voice.stop()
        except Exception as error:
            print("Voice shutdown error:", error)
        try:
            self.brain.shutdown()
        except Exception as error:
            print("Brain shutdown error:", error)
        event.accept()
