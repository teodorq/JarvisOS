from __future__ import annotations
from typing import Any
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from app.client_experience.controller import ClientExperienceController
from app.gui.client_theme import ClientTheme
from app.gui.client_hud_backdrop import ClientHudBackdrop
from app.gui.client_hud_panels import build_client_hud_row
from app.gui.cinematic_entity_widget import CinematicEntityWidget
from app.gui.client_owner_access import ClientOwnerAccess
from app.gui.client_state_presenter import ClientStatePresenter
from app.gui.client_v12_mixin import ClientV12Mixin
from app.gui.client_online_mixin import ClientOnlineMixin
from app.gui.client_voice_mixin import ClientVoiceMixin
from app.gui.client_input_policy import should_block_client_input
from app.gui.client_experience_v2 import ClientExperienceV2
from app.gui.client_window_mode import ClientWindowModeRuntime
from app.gui.user_text_widgets import clean_user_visible_widgets, naturalize_user_text
class ClientExperienceWindow(ClientVoiceMixin, ClientOnlineMixin, ClientV12Mixin, QMainWindow):
    """B116-B120 simplified client shell while owner tools remain separate."""
    STATE_MAP = {
        "ANALIZA": ("thinking", "MYŚLĘ"),
        "MYŚLĘ": ("thinking", "MYŚLĘ"),
        "DZIAŁAM": ("acting", "DZIAŁAM"),
        "RETRY": ("warning", "PONAWIAM"),
        "OCZEKIWANIE": ("warning", "CZEKAM NA POTWIERDZENIE"),
        "GOTOWY": ("idle", "JESTEM GOTOWY"),
        "ANULOWANE": ("warning", "ANULOWANO"),
        "ODRZUCONE": ("error", "NIE MOGĘ TEGO WYKONAĆ"),
        "ODMOWA": ("error", "BRAK UPRAWNIEŃ"),
        "BŁĄD": ("error", "WYMAGANA UWAGA"),
        "BLAD": ("error", "WYMAGANA UWAGA"),
    }
    def __init__(
        self,
        controller: ClientExperienceController,
        owner_window: Any,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.owner_window = owner_window
        self._last_log = ""
        self._stable_armed = False
        self._beta12_armed = False
        self._online_rc_armed = False
        self.setWindowTitle("JARVIS OS")
        self.setMinimumSize(980, 680)
        self.resize(1260, 820)
        self.setStyleSheet(ClientTheme.stylesheet())
        self._build(); clean_user_visible_widgets(self)
        self.experience_v2 = ClientExperienceV2(self)
        self.window_mode = ClientWindowModeRuntime(self)
        self.presenter = ClientStatePresenter(
            self,
            self.halo,
            self.state_label,
            self.message_label,
            self.activity_label,
            self.activity_progress,
            self.confirm_frame,
        )
        self.owner_access = ClientOwnerAccess(self, self.controller.project_root, self._show_owner_mode)
        self.owner_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F12"), self)
        self.owner_shortcut.activated.connect(self.owner_access.request_unlock)
        client_signal = getattr(self.owner_window, "client_event_signal", None)
        if client_signal is not None and hasattr(client_signal, "connect"):
            client_signal.connect(self._on_client_event)
        self._load_profile()
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_from_owner)
        self._sync_timer.start(5000); QTimer.singleShot(0, self._schedule_proactive_brief)
    def _build(self) -> None:
        root = ClientHudBackdrop()
        root.setObjectName("ClientRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(self._top_bar())
        self.stack = QStackedWidget()
        self.setup_page = self._setup_page()
        self.client_page = self._client_page()
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.client_page)
        layout.addWidget(self.stack, 1)
        footer = QLabel(
            "PRYWATNY ASYSTENT • WAŻNE DZIAŁANIA WYMAGAJĄ POTWIERDZENIA"
        )
        footer.setObjectName("ClientHint")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer); footer.hide()
    def _top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ClientTopBar")
        row = QHBoxLayout(frame)
        row.setContentsMargins(18, 12, 14, 12)
        identity = QVBoxLayout()
        identity.setSpacing(0)
        brand = QLabel("JARVIS OS")
        brand.setObjectName("ClientBrand")
        subtitle = QLabel("TWÓJ INTELIGENTNY ASYSTENT")
        subtitle.setObjectName("ClientSubtitle")
        identity.addWidget(brand)
        identity.addWidget(subtitle)
        row.addLayout(identity)
        row.addStretch(1)
        self.stable_label = QLabel("JARVIS ONLINE")
        self.stable_label.setObjectName("ClientHealthy")
        row.addWidget(self.stable_label)
        owner = QPushButton()
        owner.setObjectName("ClientSecondary")
        owner.clicked.connect(lambda: self.owner_access.request_unlock())
        owner.hide()
        self.owner_button = owner
        return frame
    def _setup_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        card = QFrame()
        card.setObjectName("SetupCard")
        card.setMaximumWidth(720)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        content = QVBoxLayout(card)
        content.setContentsMargins(34, 30, 34, 30)
        content.setSpacing(16)
        title = QLabel("PIERWSZE URUCHOMIENIE")
        title.setObjectName("ClientState")
        subtitle = QLabel(
            "Ustaw podstawy. Wszystko pozostaje lokalnie na tym komputerze."
        )
        subtitle.setObjectName("ClientMessage")
        subtitle.setWordWrap(True)
        content.addWidget(title)
        content.addWidget(subtitle)
        content.addSpacing(8)
        name_label = QLabel("Jak mam się do Ciebie zwracać?")
        name_label.setObjectName("ClientHint")
        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("Twoje imię")
        content.addWidget(name_label)
        content.addWidget(self.name_entry)
        voice_label = QLabel("Obsługa głosowa")
        voice_label.setObjectName("ClientHint")
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("Włączona", True)
        self.voice_combo.addItem("Wyłączona", False)
        content.addWidget(voice_label)
        content.addWidget(self.voice_combo)
        mode_label = QLabel("Sposób rozmowy")
        mode_label.setObjectName("ClientHint")
        self.interaction_combo = QComboBox()
        self.interaction_combo.addItem("Głos i tekst", "VOICE_AND_TEXT")
        self.interaction_combo.addItem("Tylko tekst", "TEXT_ONLY")
        content.addWidget(mode_label)
        content.addWidget(self.interaction_combo)
        safety = QLabel(
            "● Ważne działania zawsze wymagają Twojej zgody\n"
            "● Twoje dane pozostają pod kontrolą użytkownika"
        )
        safety.setObjectName("ClientHealthy")
        safety.setWordWrap(True)
        content.addWidget(safety)
        start = QPushButton("ZAPISZ I URUCHOM JARVISA")
        start.setObjectName("ClientPrimary")
        start.clicked.connect(self._save_setup)
        content.addWidget(start)
        self.setup_feedback = QLabel("")
        self.setup_feedback.setObjectName("ClientWarning")
        content.addWidget(self.setup_feedback)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(card, 1)
        centered.addStretch(1)
        outer.addLayout(centered)
        outer.addStretch(1)
        return page
    def _client_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        main = QFrame()
        main.setObjectName("ClientCard")
        content = QVBoxLayout(main)
        content.setContentsMargins(28, 20, 28, 22)
        content.setSpacing(10)
        content.addStretch(1)
        self.halo = CinematicEntityWidget()
        content.addLayout(build_client_hud_row(self, self.halo))
        self.state_label = QLabel("JESTEM GOTOWY")
        self.state_label.setObjectName("ClientState")
        self.state_label.setAlignment(Qt.AlignCenter)
        content.addWidget(self.state_label)
        self.message_label = QLabel("Powiedz lub wpisz, czego potrzebujesz.")
        self.message_label.setObjectName("ClientResultText")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumHeight(72)
        content.addWidget(self.message_label)
        self.activity_label = QLabel("Gotowy do działania.")
        self.activity_label.setObjectName("ClientHint")
        self.activity_label.setAlignment(Qt.AlignCenter)
        content.addWidget(self.activity_label)
        self.activity_progress = QProgressBar()
        self.activity_progress.setObjectName("ClientProgress")
        self.activity_progress.setRange(0, 100)
        self.activity_progress.setValue(0)
        self.activity_progress.setTextVisible(True)
        self.activity_progress.hide()
        self.activity_progress.setFormat("%p%")
        content.addWidget(self.activity_progress)
        self.confirm_frame = QFrame()
        confirm_row = QHBoxLayout(self.confirm_frame)
        confirm_row.setContentsMargins(0, 4, 0, 4)
        confirm_row.addStretch(1)
        yes = QPushButton("TAK, WYKONAJ")
        yes.setObjectName("ClientConfirm")
        yes.clicked.connect(lambda: self._submit_text("TAK"))
        no = QPushButton("NIE, ANULUJ")
        no.setObjectName("ClientCancel")
        no.clicked.connect(lambda: self._submit_text("NIE"))
        confirm_row.addWidget(yes)
        confirm_row.addWidget(no)
        confirm_row.addStretch(1)
        self.confirm_frame.hide()
        content.addWidget(self.confirm_frame)
        input_row = QHBoxLayout()
        self.command_entry = QLineEdit()
        self.command_entry.setPlaceholderText("Napisz polecenie dla Jarvisa…")
        self.command_entry.returnPressed.connect(self._submit_entry)
        send = QPushButton("WYŚLIJ")
        send.setObjectName("ClientPrimary")
        send.clicked.connect(self._submit_entry)
        self.listen_button = QPushButton("MÓW")
        self.listen_button.setObjectName("ClientSecondary")
        self.listen_button.clicked.connect(self._listen_hint)
        input_row.addWidget(self.command_entry, 1)
        input_row.addWidget(self.listen_button)
        input_row.addWidget(send)
        content.addLayout(input_row)
        quick_row = QHBoxLayout()
        quick_commands = (
            ("MÓJ DZIEŃ", "Pokaż mój plan na dziś"),
            ("POCZTA", "Znajdź najważniejszą wiadomość"),
            ("KALENDARZ", "Co mam dziś w kalendarzu?"),
            ("DOKUMENTY", "Znajdź ostatnio używany dokument"),
            ("PRZYPOMNIENIA", "Pokaż najbliższe przypomnienia"),
            ("STATUS", "Status asystenta"),
        )
        self.quick_buttons = []
        for label, command in quick_commands:
            button = QPushButton(label)
            button.setObjectName("ClientSecondary")
            button.clicked.connect(
                lambda _checked=False, value=command: self._submit_text(value)
            )
            self.quick_buttons.append(button)
            quick_row.addWidget(button)
        content.addLayout(quick_row)
        content.addStretch(1)
        outer.addWidget(main, 1)
        readiness = QFrame()
        readiness.setObjectName("ClientCard")
        row = QHBoxLayout(readiness)
        row.setContentsMargins(16, 10, 16, 10)
        self.readiness_text = QLabel("B116–B120: gotowość nie została jeszcze sprawdzona.")
        self.readiness_text.setObjectName("ClientHint")
        row.addWidget(self.readiness_text, 1)
        self.audit_button = QPushButton("SPRAWDŹ GOTOWOŚĆ 1.1")
        self.audit_button.setObjectName("ClientSecondary")
        self.audit_button.clicked.connect(self._run_or_confirm_stable)
        row.addWidget(self.audit_button)
        outer.addWidget(readiness)
        readiness.hide()
        beta12 = QFrame()
        beta12.setObjectName("ClientCard")
        beta_row = QHBoxLayout(beta12)
        beta_row.setContentsMargins(16, 10, 16, 10)
        self.beta12_text = QLabel("B121–B125: gotowość Business 1.2 Beta nie została sprawdzona.")
        self.beta12_text.setObjectName("ClientHint")
        beta_row.addWidget(self.beta12_text, 1)
        self.beta12_button = QPushButton("SPRAWDŹ BUSINESS 1.2 BETA")
        self.beta12_button.setObjectName("ClientSecondary")
        self.beta12_button.clicked.connect(self._run_or_confirm_v12_beta)
        beta_row.addWidget(self.beta12_button)
        outer.addWidget(beta12)
        beta12.hide()
        online = QFrame()
        online.setObjectName("ClientCard")
        online_row = QHBoxLayout(online)
        online_row.setContentsMargins(16, 10, 16, 10)
        self.online_text = QLabel(
            "B126–B130: Google Workspace nie jest jeszcze połączony."
        )
        self.online_text.setObjectName("ClientHint")
        online_row.addWidget(self.online_text, 1)
        self.online_button = QPushButton("SPRAWDŹ BUSINESS 1.2 STABLE RC")
        self.online_button.setObjectName("ClientSecondary")
        self.online_button.clicked.connect(self._run_or_confirm_online_rc)
        online_row.addWidget(self.online_button)
        outer.addWidget(online)
        online.hide()
        return page
    def _load_profile(self) -> None:
        status = self.controller.status()
        profile = status["profile"]
        self.name_entry.setText(profile["display_name"])
        self.voice_combo.setCurrentIndex(0 if profile["voice_enabled"] else 1)
        mode_index = self.interaction_combo.findData(profile["interaction_mode"])
        self.interaction_combo.setCurrentIndex(max(0, mode_index))
        self.stack.setCurrentWidget(
            self.client_page if profile["setup_completed"] else self.setup_page
        )
        self._update_stable_status(status)
        self._update_v12_status()
        self._sync_online_status()
    def _save_setup(self) -> None:
        name = self.name_entry.text().strip()
        if not name:
            self.setup_feedback.setText("Wpisz imię lub nazwę użytkownika.")
            return
        profile = self.controller.configure(
            display_name=name,
            voice_enabled=bool(self.voice_combo.currentData()),
            interaction_mode=self.interaction_combo.currentData(),
        )
        self.message_label.setText(f"Witaj {profile['display_name']}. Jestem gotowy.")
        self.stack.setCurrentWidget(self.client_page)
        self.controller.set_mode("CLIENT")
        self._schedule_proactive_brief()
    def _submit_entry(self) -> None:
        text = self.command_entry.text().strip()
        if not text:
            return
        self.command_entry.clear()
        self._submit_text(text)
    def _submit_text(self, text: str) -> None:
        value = str(text).strip()
        has_pending_confirmation = (
            getattr(self.owner_window, "pending_thought", None) is not None
        )
        if should_block_client_input(
            presenter_busy=bool(self.presenter.busy),
            has_pending_confirmation=has_pending_confirmation,
        ):
            self.activity_label.setText("Najpierw zakończę bieżące zadanie.")
            return
        self.presenter.begin_command()
        self.controller.set_halo("thinking", "Analizuję polecenie")
        QTimer.singleShot(
            25,
            lambda command=value: self.owner_window.process_client_command(command),
        )
    def _sync_from_owner(self) -> None:
        # B136: klient nie odczytuje konsoli, logów ani historii właściciela.
        return
    def _on_client_event(self, raw_event: object) -> None:
        event = self.presenter.apply_event(raw_event)
        self.controller.set_halo(
            event.get("state", "idle"),
            self.message_label.text(),
        )

    def _map_state(self, value: str) -> tuple[str, str]:
        upper = value.upper()
        for marker, result in self.STATE_MAP.items():
            if marker in upper:
                return result
        return "acting", "DZIAŁAM"
    def _run_or_confirm_stable(self) -> None:
        if self._stable_armed:
            try:
                confirmation = self.controller.confirm_stable()
            except ValueError as error:
                self.readiness_text.setText(naturalize_user_text(error))
                return
            self.readiness_text.setText("Business 1.1 Stable gotowy. Publikacja automatyczna: NIE.")
            self.audit_button.setText("BUSINESS 1.1 STABLE")
            self.audit_button.setEnabled(False)
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.stable_label.style().unpolish(self.stable_label)
            self.stable_label.style().polish(self.stable_label)
            self.message_label.setText(naturalize_user_text(confirmation["status"]))
            return
        audit = self.controller.run_usability_audit(
            width=self.width(),
            height=self.height(),
            animation_running=self.halo.animation_running,
            owner_switch_available=self.owner_button.isEnabled(),
            command_input_available=self.command_entry.isEnabled(),
        )
        self.readiness_text.setText(
            f"Audyt gotowości: {audit['passed']}/{audit['total']} warunków spełnionych."
        )
        if audit["status"] == "PASSED":
            self._stable_armed = True
            self.audit_button.setText("POTWIERDŹ BUSINESS 1.1 STABLE")
    def _update_stable_status(self, status: dict[str, Any]) -> None:
        if status["stable_ready"]:
            self.stable_label.setText("JARVIS ONLINE")
            self.stable_label.setObjectName("ClientHealthy")
            self.readiness_text.setText("Business 1.1 Stable jest potwierdzony lokalnie.")
            self.audit_button.setText("BUSINESS 1.1 STABLE")
            self.audit_button.setEnabled(False)
        elif status["latest_audit_status"] == "PASSED":
            self._stable_armed = True
            self.audit_button.setText("POTWIERDŹ BUSINESS 1.1 STABLE")
    def _show_owner_mode(self) -> None:
        prepare = getattr(self.owner_window, "_ensure_owner_interface", None)
        if callable(prepare): prepare()
        self.controller.set_mode("OWNER")
        self.window_mode.leave(); self.hide()
        self.owner_window.show()
        self.owner_window.raise_()
        self.owner_window.activateWindow()
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.window_mode.close(); mode = "CLIENT" if self.controller.status()["profile"]["setup_completed"] else "OWNER"
        self.controller.set_mode(mode)
        if self.owner_window is not None:
            runtime = getattr(self.owner_window, "_client_background_commands", None)
            runtime.shutdown() if runtime is not None else None
            self.owner_window.close()
        event.accept()
