from __future__ import annotations
import re
from typing import Any
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget
from app.ai.brain import Brain
from app.assistant.controller import PersonalAssistantController
from app.business.business_config import BusinessConfigStore
from app.business.business_edition_service import BusinessEditionService
from app.core.project_paths import resolve_project_root
from app.client_experience.controller import ClientExperienceController
from app.gui.business_command_runtime import BusinessCommandRuntimeMixin
from app.gui.confirmation_revision_runtime import handle_owner_confirmation, remember_confirmed_calendar_write
from app.gui.client_experience_window import ClientExperienceWindow
from app.gui.owner_access_setup import ensure_owner_pin
from app.gui.business_display import display_environment, display_status, same_identity
from app.gui.business_pages import ConsolePage, SettingsPage, TrustPage
from app.gui.business_platform_page import BusinessPlatformPage
from app.gui.business_operations_page import BusinessOperationsPage
from app.gui.business_release_page import BusinessReleasePage
from app.gui.business_commercial_page import BusinessCommercialPage
from app.gui.assistant_productivity_page import AssistantProductivityPage
from app.gui.intelligence_center_page import IntelligenceCenterPage
from app.gui.productivity_center_page import ProductivityCenterPage
from app.gui.stability_beta_page import StabilityBetaPage
from app.gui.assistant_v12_page import AssistantV12Page
from app.gui.online_assistant_page import OnlineAssistantPage; from app.gui.forex_paper_page import ForexPaperPage
from app.gui.business_theme import BusinessTheme
from app.gui.business_widgets import MetricCard, NavigationButton, StatusPill
from app.gui.business_status_snapshot import business_service_snapshot
from app.gui.main_window_runtime import connect_main_runtime, prepare_owner_interface
from app.system.monitor import SystemMonitor
from app.voice.voice_listener import VoiceListener
LEGACY_UI_LABELS = ("BUSINESS COMMAND CENTER", "COMMAND CONSOLE", "ORGANIZATION", "LICENSE & TRUST", "OWNER DEVELOPMENT LICENSE")
UI_COMPATIBILITY_MARKER = "B80.2 FINAL UI"
class MainWindow(BusinessCommandRuntimeMixin, QMainWindow):
    """B81–B130 platforma właścicielska z odseparowanym trybem klienta."""
    voice_text_signal = Signal(str)
    client_event_signal = Signal(object)
    def __init__(self) -> None:
        super().__init__()
        self.project_root = resolve_project_root()
        self._interface_ready = False
        self._voice_runtime_connected = False
        self._client_start_requested = ClientExperienceController(
            self.project_root
        ).should_start_client()
        self.config_store = BusinessConfigStore(self.project_root)
        self.business_config = self.config_store.ensure()
        self.business_service = BusinessEditionService(self.project_root)
        self.brain = Brain(runtime_profile="client" if self._client_start_requested else "owner")
        self.assistant = PersonalAssistantController(self.project_root, memory=self.brain.memory)
        self.brain.personal_assistant_controller = self.assistant
        self.monitor = SystemMonitor()
        self.pending_thought: dict | None = None
        self._client_async_enabled = True
        self._client_scope_enforced = True
        self._owner_async_enabled = True
        self.client_window = None
        self.voice = None
        self.voice_online = False
        self._status_tick = 0
        self._initialize_voice()
        self._configure_window()
        if not self._client_start_requested:
            self._ensure_owner_interface()
        self._connect_runtime()
    def _initialize_voice(self) -> None:
        try:
            self.voice = VoiceListener(on_text=self.handle_voice_text_safe, settings=self.assistant.voice.settings())
            self.voice_online = True
        except Exception as error:
            self.voice = None
            self.voice_online = False
            print("Voice OFF:", error)
    def _configure_window(self) -> None:
        self.setWindowTitle(str(self.business_config["product_name"]))
        self.setMinimumSize(1240, 800)
        self.resize(1460, 900)
        self._apply_theme()
    def _ensure_owner_interface(self) -> None:
        enable = getattr(self.brain, "enable_owner_runtime", None); enable() if callable(enable) else None; prepare_owner_interface(self)
    def _apply_theme(self) -> None:
        self.setStyleSheet(
            BusinessTheme.stylesheet(str(self.business_config["accent_color"]))
        )
    def _build_interface(self) -> None:
        root = QWidget()
        root.setObjectName("BusinessRoot")
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 14, 16, 12)
        main_layout.setSpacing(10)
        main_layout.addWidget(self._build_header())
        main_layout.addLayout(self._build_metrics())
        self.page_context = QLabel("KONSOLA • AUTONOMIA Z POTWIERDZENIEM")
        self.page_context.setObjectName("Muted")
        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_workspace(), 1)
        main_layout.addLayout(body, 1)
        footer_row = QHBoxLayout()
        footer_row.addWidget(self.page_context)
        footer_row.addStretch(1)
        footer = QLabel("BUSINESS 1.2 STABLE RC • LOKALNY TRYB WŁAŚCICIELA")
        footer.setObjectName("Muted")
        footer_row.addWidget(footer)
        main_layout.addLayout(footer_row)
        self.system_status = QLabel()
        self.system_status.hide()
    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 11, 18, 11)
        identity = QVBoxLayout()
        identity.setSpacing(0)
        self.product_title = QLabel("JARVIS OS")
        self.product_title.setObjectName("ProductTitle")
        subtitle = QLabel("BIZNESOWE CENTRUM DOWODZENIA")
        subtitle.setObjectName("ProductSubtitle")
        identity.addWidget(self.product_title)
        identity.addWidget(subtitle)
        layout.addLayout(identity)
        layout.addStretch(1)
        self.organization_pill = StatusPill(
            str(self.business_config["organization"]), "neutral"
        )
        self.environment_pill = StatusPill(
            display_environment(self.business_config["environment"]), "accent"
        )
        self.license_pill = StatusPill("OWNER DEVELOPMENT LICENSE", "neutral")
        self.license_pill.hide()
        self.header_system = StatusPill("SYSTEM GOTOWY", "healthy")
        client_mode = QPushButton("TRYB KLIENTA"); client_mode.setObjectName("SecondaryButton")
        client_mode.clicked.connect(self._open_client_mode); layout.addWidget(client_mode)
        layout.addWidget(self.organization_pill)
        layout.addWidget(self.environment_pill)
        layout.addWidget(self.license_pill)
        layout.addWidget(self.header_system)
        return header
    def show_start_mode(self) -> None:
        if self._client_start_requested: QTimer.singleShot(0, self._open_client_mode); return
        self._ensure_owner_interface(); self.show()
    def _open_client_mode(self) -> None:
        if not ensure_owner_pin(self, self.project_root): return
        if self.client_window is None: self.client_window = ClientExperienceWindow(ClientExperienceController(self.project_root), self)
        self.client_window.showMaximized(); self.client_window.window_mode.show_conversation(); self.client_window.raise_(); self.client_window.activateWindow()
        self.hide()
    def _build_metrics(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setHorizontalSpacing(8)
        self.metric_cards = {
            "cpu": MetricCard("CPU"),
            "ram": MetricCard("RAM"),
            "disk": MetricCard("DYSK C"),
            "uptime": MetricCard("CZAS PRACY", hint="SESJA"),
        }
        for column, card in enumerate(self.metric_cards.values()):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(card, 0, column)
        return layout
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        heading = QLabel("NAWIGACJA BIZNESOWA")
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.navigation_buttons: dict[str, NavigationButton] = {}
        navigation = (
            ("KONSOLA OPERACYJNA", "console"),
            ("ORGANIZACJA", "settings"),
            ("LICENCJA I ZAUFANIE", "trust"),
            ("PROFILE, LICENCJE I ROLE", "platform"),
            ("AUDYT, BACKUPY I AKTUALIZACJE", "operations"),
            ("WDROŻENIE I RELEASE RC1", "release"),
            ("PRODUKCJA I SPRZEDAŻ", "commercial"),
            ("ASYSTENT I CODZIENNA PRACA", "assistant"),
            ("CENTRUM INTELIGENCJI", "intelligence"),
            ("PRODUKTYWNOŚĆ I ORGANIZACJA", "productivity"),
            ("STABILNOŚĆ I BUSINESS BETA", "stability"), ("FOREX PAPER", "forex"), ("ASYSTENT 1.2 BETA", "assistant_v12"), ("ASYSTENT ONLINE I RC", "online"),
        )
        for label, page_name in navigation:
            button = NavigationButton(label, page_name)
            button.clicked.connect(
                lambda _checked=False, value=page_name: self._show_page(value)
            )
            self.navigation_group.addButton(button)
            self.navigation_buttons[page_name] = button
            layout.addWidget(button)
        layout.addSpacing(10)
        services_title = QLabel("PRZEGLĄD SYSTEMU")
        services_title.setObjectName("SectionTitle")
        layout.addWidget(services_title)
        self.modules = QLabel()
        self.modules.setWordWrap(True)
        self.modules.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.modules)
        layout.addStretch(1)
        security = QFrame()
        security.setObjectName("SecurityCard")
        security_layout = QVBoxLayout(security)
        security_layout.setContentsMargins(12, 10, 12, 10)
        security_title = QLabel("WYMUSZONE BEZPIECZEŃSTWO")
        security_title.setObjectName("SectionTitle")
        security_status = QLabel(
            "● AUTO-APPROVE: WYŁĄCZONE\n"
            "● POTWIERDZENIE: WYMAGANE\n"
            "● AKTYWNE WYKONANIA: MAKS. 1\n"
            "● KOD ZDALNY: WYŁĄCZONY"
        )
        security_status.setObjectName("Healthy")
        security_layout.addWidget(security_title)
        security_layout.addWidget(security_status)
        layout.addWidget(security)
        return sidebar
    def _build_workspace(self) -> QFrame:
        workspace = QFrame()
        workspace.setObjectName("Workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(12, 12, 12, 12)
        self.stack = QStackedWidget()
        self.console_page = ConsolePage()
        self.settings_page = SettingsPage()
        self.trust_page = TrustPage()
        self.platform_page = BusinessPlatformPage(self.business_service)
        self.operations_page = BusinessOperationsPage(self.business_service)
        self.release_page = BusinessReleasePage(self.business_service)
        self.commercial_page = BusinessCommercialPage(self.business_service)
        self.assistant_page = AssistantProductivityPage(self.assistant)
        self.intelligence_page = IntelligenceCenterPage(self.assistant.intelligence)
        self.productivity_page = ProductivityCenterPage(self.assistant.productivity)
        self.stability_page = StabilityBetaPage(self.assistant.stability); self.forex_page = ForexPaperPage(self.assistant.trading.forex_dashboard); self.assistant_v12_page = AssistantV12Page(self.assistant.assistant_v12); self.online_page = OnlineAssistantPage(self.assistant.online)
        self.pages = {
            "console": self.console_page,
            "settings": self.settings_page,
            "trust": self.trust_page,
            "platform": self.platform_page, "operations": self.operations_page,
            "release": self.release_page, "commercial": self.commercial_page,
            "assistant": self.assistant_page, "intelligence": self.intelligence_page,
            "productivity": self.productivity_page, "stability": self.stability_page, "forex": self.forex_page, "assistant_v12": self.assistant_v12_page, "online": self.online_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        layout.addWidget(self.stack)
        self.console_page.command_submitted.connect(self._process_typed_command)
        self.console_page.quick_command_requested.connect(
            self.console_page.prepare_command
        )
        self.settings_page.save_requested.connect(self._save_business_settings)
        self.settings_page.reset_requested.connect(self._reset_business_settings)
        self.trust_page.refresh_requested.connect(self._refresh_business_status)
        self.operations_page.command_requested.connect(
            lambda command: (self.console_page.prepare_command(command), self._show_page("console"))
        )
        self.release_page.command_requested.connect(
            lambda command: (self.console_page.prepare_command(command), self._show_page("console"))
        )
        self.commercial_page.command_requested.connect(
            lambda command: (self.console_page.prepare_command(command), self._show_page("console"))
        )
        for command_page in (self.assistant_page, self.intelligence_page, self.productivity_page, self.stability_page, self.assistant_v12_page, self.online_page):
            command_page.command_requested.connect(lambda command: (self.console_page.prepare_command(command), self._show_page("console")))
        self.platform_page.configuration_changed.connect(
            lambda: (
                setattr(self, "business_config", self.config_store.ensure()),
                self._apply_runtime_config(),
            )
        )
        self.settings_page.load_config(self.business_config)
        self.console_page.show_quick_actions(
            bool(dict(self.business_config.get("ui", {}) or {}).get(
                "show_quick_actions", True
            ))
        )
        self._append_welcome_messages()
        start_page = str(
            dict(self.business_config.get("ui", {}) or {}).get(
                "start_page", "console"
            )
        )
        self._show_page(start_page if start_page in self.pages else "console")
        return workspace
    def _show_page(self, page_name: str) -> None:
        page = self.pages.get(page_name, self.console_page)
        self.stack.setCurrentWidget(page)
        for name, button in self.navigation_buttons.items():
            button.setChecked(name == page_name)
        contexts = {
            "console": "KONSOLA • AUTONOMIA Z POTWIERDZENIEM",
            "settings": "ORGANIZACJA • ATOMOWA KONFIGURACJA LOKALNA",
            "trust": "LICENCJA • INTEGRALNOŚĆ SHA-256 • BEZPIECZEŃSTWO",
            "platform": "PROFILE • LICENCJE • ROLE I UPRAWNIENIA",
            "operations": "AUDYT • KOPIE ZAPASOWE • ODZYSKIWANIE • AKTUALIZACJE",
            "release": "INSTALATOR • PIERWSZE URUCHOMIENIE • WYDANIE RC1",
            "commercial": "PRODUKCJA • LICENCJE • DYSTRYBUCJA • SPRZEDAŻ",
            "assistant": "ROZMOWA • PULPIT • PAMIĘĆ • GŁOS • CODZIENNA PRACA",
            "intelligence": "WIZJA • MÓZG • PULPIT • PAMIĘĆ • AUTONOMIA",
            "productivity": "POCZTA • KALENDARZ • DOKUMENTY • PRZYPOMNIENIA • RAPORT",
            "stability": "SCENARIUSZE • WYDAJNOŚĆ • ODZYSKIWANIE • RESTART • BUSINESS BETA", "forex": "PAPER ONLY • POZYCJE • SL • TP • WYNIK", "assistant_v12": "ROZMOWA • KONTEKST • WYBÓR NARZĘDZI • POSTĘP • BUSINESS 1.2 BETA", "online": "GOOGLE WORKSPACE • PRZEPŁYW PRACY • DOKUMENTY • STABLE RC • 1.3 BETA",
        }
        page_context = getattr(self, "page_context", None)
        if page_context is not None:
            page_context.setText(contexts.get(page_name, contexts["console"]))
    def _append_welcome_messages(self) -> None:
        organization = str(self.business_config["organization"])
        self.console_page.append(
            f"Jarvis: Witaj {organization}. Biznesowe centrum dowodzenia jest online."
        )
        self.console_page.append("Jarvis: Business 1.2 Stable RC oraz Asystent Online 1.3 Beta są gotowe.")
        self.console_page.append(
            "Jarvis: Automatyczne zatwierdzanie jest wyłączone. Ważne działania wymagają Twojej zgody."
        )
        self.console_page.append("Jarvis: Monitoruję system i gotowość najważniejszych usług.")
        self.console_page.append(
            "Jarvis: Głos ONLINE. Powiedz polecenie lub wpisz je ręcznie."
            if self.voice_online else
            "Jarvis: Głos OFFLINE. Wpisz polecenie ręcznie."
        )
    def _connect_runtime(self) -> None:
        connect_main_runtime(self)
    def update_system_status(self) -> None:
        cpu = self.monitor.get_cpu_usage()
        ram = self.monitor.get_ram_usage()
        disk = self.monitor.get_disk_usage()
        uptime = self.monitor.get_uptime()
        values = {"cpu": cpu, "ram": ram, "disk": disk, "uptime": uptime}
        for key, value in values.items():
            self.metric_cards[key].set_value(value)
        self.metric_cards["cpu"].set_hint(self._metric_hint(cpu, 70, 90))
        self.metric_cards["ram"].set_hint(self._metric_hint(ram, 75, 90))
        self.metric_cards["disk"].set_hint(self._metric_hint(disk, 80, 92))
        background, online_connected = business_service_snapshot(self)
        voice = "ONLINE" if self.voice_online else "OFFLINE"
        self.modules.setText(
            "USŁUGI GŁÓWNE\n\n"
            "● Mózg: ONLINE\n"
            "● Wizja: GOTOWA\n"
            "● Pulpit: ONLINE\n"
            "● Pamięć: AKTYWNA\n"
            f"● Głos: {voice}\n\n"
            "AUTONOMIA\n\n"
            f"● AutoDev w tle: {display_status(background)}\n"
            "● Centrum sterowania: DOSTĘPNE\n"
            "● Monitorowanie incydentów: DOSTĘPNE\n"
            "● Odzyskiwanie: DOSTĘPNE\n"
            "● Produkcja: ZABEZPIECZONA\n\n"
            "EDYCJA\n\n"
            "● Platforma: GOTOWA\n"
            "● Operacje: GOTOWE\n"
            "● Wdrożenie: DOSTĘPNE\n"
            "● Produkcja: KONTROLOWANA\n"
            "● Asystent: GOTOWY\n"
            "● Inteligencja: GOTOWA\n"
            "● Produktywność: GOTOWA\n"
            "● Stabilność: GOTOWA\n"
            f"● Tryb klienta: GOTOWY\n● Asystent 1.2: GOTOWY\n● Usługi online: {'POŁĄCZONE' if online_connected else 'OCZEKUJĄ NA GOOGLE'}"
        )
        self.header_system.set_status("SYSTEM GOTOWY", "healthy")
        self._status_tick += 1
        if self._status_tick % 15 == 0:
            self._refresh_business_status()
    @staticmethod
    def _metric_hint(value: object, warning: float, critical: float) -> str:
        match = re.search(r"\d+(?:[.,]\d+)?", str(value))
        if not match:
            return "BRAK DANYCH"
        number = float(match.group(0).replace(",", "."))
        if number >= critical:
            return "KRYTYCZNY"
        if number >= warning:
            return "UWAGA"
        return "OK"
    def _refresh_business_status(self) -> None:
        try:
            status = self.business_service.status()
            self.trust_page.load_status(status)
            license_status = dict(status.get("license", {}) or {})
            label = str(license_status.get("status", "UNKNOWN"))
            active = bool(license_status.get("active"))
            visible_label = display_status(label)
            environment = self.business_config.get("environment", "")
            show_header_license = not same_identity(label, environment)
            self.license_pill.set_status(
                f"LICENCJA: {visible_label}",
                "accent" if active else "danger",
            )
            self.license_pill.setVisible(show_header_license or not active)
            self.console_page.set_license(
                "LICENCJA AKTYWNA" if active else "SPRAWDŹ LICENCJĘ",
                active,
            )
        except Exception as error:
            self.license_pill.set_status("BŁĄD LICENCJI", "danger")
            self.license_pill.show()
            self.console_page.set_license("BŁĄD LICENCJI", False)
            print("Business status error:", error)
    def _save_business_settings(self, updates: dict[str, Any]) -> None:
        try:
            self.business_config = self.config_store.update(updates)
            self._apply_runtime_config()
            self.settings_page.set_feedback("Konfiguracja zapisana bezpiecznie.", True)
            self.console_page.append("Jarvis: Konfiguracja Business Edition została zapisana.")
        except Exception as error:
            self.settings_page.set_feedback(f"Błąd zapisu: {error}", False)
    def _reset_business_settings(self) -> None:
        try:
            self.business_config = self.config_store.reset()
            self._apply_runtime_config()
            self.settings_page.set_feedback("Przywrócono bezpieczne ustawienia domyślne.", True)
            self.console_page.append("Jarvis: Przywrócono domyślną konfigurację Business Edition.")
        except Exception as error:
            self.settings_page.set_feedback(f"Błąd resetu: {error}", False)
    def _apply_runtime_config(self) -> None:
        self.setWindowTitle(str(self.business_config["product_name"]))
        self.organization_pill.setText(str(self.business_config["organization"]))
        self.environment_pill.setText(
            display_environment(self.business_config["environment"])
        )
        self.settings_page.load_config(self.business_config)
        self.console_page.show_quick_actions(
            bool(dict(self.business_config.get("ui", {}) or {}).get(
                "show_quick_actions", True
            ))
        )
        self._apply_theme()
        self._refresh_business_status()
    def handle_confirmation(self, answer: str) -> None:
        if callable(getattr(super(), "handle_confirmation", None)):
            super().handle_confirmation(answer)
            return
        handle_owner_confirmation(self, answer)
