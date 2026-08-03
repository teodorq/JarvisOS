from __future__ import annotations

from PySide6.QtCore import QTimer

from app.gui.client_live_conflict_refresh import ClientLiveConflictRefreshRuntime
from app.gui.client_safe_proactivity import ClientSafeProactivityRuntime
from app.gui.client_startup_conflict_runtime import ClientStartupConflictRuntime; from app.jarvis_experience.isolation import ClientIsolationPolicy


class ClientOnlineMixin:
    """B126-B130 client-mode status and Stable RC confirmation."""

    def _online_assistant(self):
        assistant = getattr(self.owner_window, "assistant", None)
        return getattr(assistant, "online", None)

    def _sync_online_status(self) -> None:
        controller = self._online_assistant()
        if controller is None:
            return
        status = controller.status()
        connection = dict(status.get("connection", {}) or {})
        rc = dict(status.get("rc", {}) or {})
        beta = dict(dict(status.get("v13", {}) or {}).get("beta", {}) or {})
        if beta.get("beta_ready"):
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.online_text.setText("Online Assistant 1.3 Beta jest potwierdzony lokalnie.")
            self.online_button.setText("ONLINE ASSISTANT 1.3 BETA")
            self.online_button.setEnabled(False)
        elif rc.get("rc_ready"):
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.online_text.setText("Business 1.2 Stable RC jest potwierdzony lokalnie.")
            self.online_button.setText("BUSINESS 1.2 STABLE RC")
            self.online_button.setEnabled(False)
        elif connection.get("token_present"):
            self.online_text.setText("Google Workspace jest połączony. Uruchom audyt Stable RC.")
        else:
            self.online_text.setText("Google Workspace nie jest połączony. Połącz konto w trybie właściciela.")
        self._schedule_proactive_brief()

    def _schedule_proactive_brief(self) -> None:
        if not getattr(self, "_proactive_brief_scheduled", False):
            self._proactive_brief_scheduled = True
            self._proactive_timer = QTimer(self)
            self._proactive_timer.setInterval(15 * 60 * 1000)
            self._proactive_timer.timeout.connect(self._show_proactive_brief)
            self._proactive_timer.start()
        self._startup_conflict_runtime().arm()
        self._live_conflict_refresh_runtime().arm()

    def _startup_conflict_runtime(self) -> ClientStartupConflictRuntime:
        runtime = getattr(self, "_startup_conflict_runtime_service", None)
        if runtime is None:
            runtime = ClientStartupConflictRuntime(self)
            self._startup_conflict_runtime_service = runtime
        return runtime

    def _live_conflict_refresh_runtime(self) -> ClientLiveConflictRefreshRuntime:
        runtime = getattr(self, "_live_conflict_refresh_service", None)
        if runtime is None:
            runtime = ClientLiveConflictRefreshRuntime(self)
            self._live_conflict_refresh_service = runtime
        return runtime

    def _safe_proactivity_runtime(self) -> ClientSafeProactivityRuntime:
        runtime = getattr(self, "_safe_proactivity_service", None)
        if runtime is None:
            runtime = ClientSafeProactivityRuntime(self)
            self._safe_proactivity_service = runtime
        return runtime

    def _show_startup_conflict_scan(self) -> None:
        self._startup_conflict_runtime().run()

    def _show_proactive_brief(self) -> None:
        runtime = self._safe_proactivity_runtime()  # pending_thought ends in _on_client_event
        if not runtime.request(self._show_proactive_brief_now, priority=10, kind="daily_brief"):
            return

    def _show_proactive_brief_now(self) -> None:
        try:
            profile = self.controller.status()["profile"]
            assistant = getattr(self.owner_window, "assistant", None)
            natural = getattr(assistant, "natural_actions", None)
            if natural is None:
                return
            guard = getattr(natural, "proactive_brief_guard", None)
            decision = dict(guard() or {}) if callable(guard) else {}
            if decision.get("suppress"):
                return
            result = natural.startup_brief()
        except Exception:
            return
        if not profile.get("setup_completed") or not result.get("should_show"):
            return
        level = str(result.get("level", "quiet")).lower()
        state = "important" if level in {"high", "critical"} else "brief"
        payload = {"state": state, "message": str(result.get("message", "")), "progress": 0, "requires_confirmation": False}
        self._safe_proactivity_runtime().deliver(
            payload, priority=10, kind="daily_brief"
        )
        if result.get("speak") and False:
            self.owner_window.say_safe(str(result.get("message", "")))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if hasattr(self, "presenter"):
            self._startup_conflict_runtime().arm()
            self._live_conflict_refresh_runtime().arm()

    def _run_or_confirm_online_rc(self) -> None:
        controller = self._online_assistant()
        if controller is None:
            self.online_text.setText("Asystent online nie jest dostępny.")
            return
        if self._online_rc_armed:
            try:
                confirmation = controller.confirm_rc()
            except ValueError as error:
                self.online_text.setText(ClientIsolationPolicy.sanitize_text(error))
                return
            self.online_text.setText(
                "Business 1.2 Stable RC gotowy. Automatyczna publikacja: NIE."
            )
            self.online_button.setText("BUSINESS 1.2 STABLE RC")
            self.online_button.setEnabled(False)
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.message_label.setText(ClientIsolationPolicy.sanitize_text(confirmation["status"]))
            return
        audit = controller.run_rc_audit()
        self.online_text.setText(
            f"Audyt online: {audit['passed']}/{audit['total']} warunków spełnionych."
        )
        if audit["status"] == "PASSED":
            self._online_rc_armed = True
            self.online_button.setText("POTWIERDŹ BUSINESS 1.2 STABLE RC")
