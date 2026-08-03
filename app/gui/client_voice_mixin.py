from __future__ import annotations


class ClientVoiceMixin:
    """Push-to-talk UI lifecycle independent from background wake-word mode."""

    def _listen_hint(self) -> None:
        voice = getattr(self.owner_window, "voice", None)
        if voice is None:
            self.handle_voice_state("error")
            return
        if getattr(voice, "manual_active", False):
            voice.cancel_listen_once()
            return
        self.presenter.show(
            "listening",
            "Po sygnale powiedz od razu całe polecenie.",
            progress=0,
        )
        self.controller.set_halo("listening", "Przygotowuję mikrofon")
        self.listen_button.setText("ANULUJ")
        if not voice.listen_once():
            self.handle_voice_state("busy")

    def handle_voice_state(self, state: str) -> None:
        value = str(state).strip().casefold()
        if value == "prompt":
            self.state_label.setText("SŁUCHAM")
            self.message_label.setText(
                "Po sygnale powiedz od razu całe polecenie. Nie musisz mówić „Jarvis”."
            )
            self.activity_label.setText("Uruchamiam mikrofon…")
            return
        if value == "listening":
            self.state_label.setText("SŁUCHAM")
            self.message_label.setText("Powiedz teraz swoje polecenie.")
            self.activity_label.setText("Mikrofon jest aktywny.")
            return
        self.listen_button.setText("MÓW")
        if value in {"recognized", "completed"}:
            self.presenter.begin_command()
            self.controller.set_halo("thinking", "Rozpoznano polecenie")
            self.state_label.setText("ANALIZUJĘ")
            self.activity_label.setText("Rozumiem i przygotowuję działanie…")
        elif value == "timeout":
            self.presenter.reset_idle("Nie usłyszałem polecenia. Naciśnij MÓW i spróbuj ponownie.")
        elif value == "not_understood":
            self.presenter.reset_idle("Nie zrozumiałem. Powiedz polecenie trochę wyraźniej.")
        elif value == "cancelled":
            self.presenter.reset_idle("Nasłuch został anulowany.")
        elif value == "busy":
            self.activity_label.setText("Mikrofon już pracuje.")
        elif value == "error":
            self.presenter.show("error", "Nie udało się uruchomić mikrofonu.", progress=0)
