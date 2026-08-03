from __future__ import annotations

from app.jarvis_experience.isolation import ClientIsolationPolicy


class ClientV12Mixin:
    """B121-B125 client-shell integration kept outside the B116-B120 window."""

    def _assistant_v12(self):
        assistant = getattr(self.owner_window, "assistant", None)
        return getattr(assistant, "assistant_v12", None)

    def _sync_v12_progress(self) -> None:
        controller = self._assistant_v12()
        if controller is None:
            return
        status = controller.status()
        progress = dict(status.get("progress", {}) or {})
        active = dict(progress.get("active", {}) or {})
        latest = dict(progress.get("latest", {}) or {})
        operation = active or latest
        if operation:
            percent = int(operation.get("progress_percent", 0) or 0)
            phase = str(operation.get("phase", "GOTOWE"))
            message = ClientIsolationPolicy.sanitize_text(operation.get("message", ""))
            self.activity_progress.setValue(percent)
            self.activity_label.setText(
                f"Pracuję nad zadaniem • {percent}%"
                + (f" — {message}" if message else "")
            )
            self.activity_progress.setVisible(percent < 100)
        beta = dict(status.get("beta", {}) or {})
        if beta.get("beta_ready"):
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.beta12_text.setText(
                "Business 1.2 Beta jest potwierdzony lokalnie."
            )
            self.beta12_button.setText("BUSINESS 1.2 BETA")
            self.beta12_button.setEnabled(False)

    def _run_or_confirm_v12_beta(self) -> None:
        controller = self._assistant_v12()
        if controller is None:
            self.beta12_text.setText("Asystent 1.2 nie jest dostępny.")
            return
        if self._beta12_armed:
            try:
                confirmation = controller.confirm_beta()
            except ValueError as error:
                self.beta12_text.setText(ClientIsolationPolicy.sanitize_text(error))
                return
            self.beta12_text.setText(
                "Business 1.2 Beta gotowy. Automatyczna publikacja: NIE."
            )
            self.beta12_button.setText("BUSINESS 1.2 BETA")
            self.beta12_button.setEnabled(False)
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.message_label.setText(ClientIsolationPolicy.sanitize_text(confirmation["status"]))
            return
        audit = controller.run_beta_audit()
        self.beta12_text.setText(
            "Audyt asystenta: "
            f"{audit['passed']}/{audit['total']} warunków spełnionych."
        )
        if audit["status"] == "PASSED":
            self._beta12_armed = True
            self.beta12_button.setText("POTWIERDŹ BUSINESS 1.2 BETA")

    def _update_v12_status(self) -> None:
        controller = self._assistant_v12()
        if controller is None:
            return
        beta = dict(controller.status().get("beta", {}) or {})
        if beta.get("beta_ready"):
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.beta12_text.setText(
                "Business 1.2 Beta jest potwierdzony lokalnie."
            )
            self.beta12_button.setText("BUSINESS 1.2 BETA")
            self.beta12_button.setEnabled(False)
        elif beta.get("latest_audit_status") == "PASSED":
            self._beta12_armed = True
            self.beta12_button.setText("POTWIERDŹ BUSINESS 1.2 BETA")
