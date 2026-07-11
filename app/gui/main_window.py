from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal

from app.ai.actions import ActionTypes
from app.ai.brain import Brain
from app.system.monitor import SystemMonitor
from app.voice.voice_listener import VoiceListener


class MainWindow(QMainWindow):
    voice_text_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.brain = Brain()
        self.monitor = SystemMonitor()
        self.pending_thought = None

        try:
            self.voice = VoiceListener(on_text=self.handle_voice_text_safe)
            self.voice_online = True
        except Exception as e:
            self.voice = None
            self.voice_online = False
            print("Voice OFF:", e)

        self.setWindowTitle("JARVIS OS")
        self.setMinimumSize(1150, 760)

        self.setStyleSheet("""
            QMainWindow { background-color: #050814; }
            QLabel { color: #d8f3ff; font-size: 15px; }
            QTextEdit {
                background-color: #0b1020;
                color: #e6f7ff;
                border: 1px solid #1f6feb;
                border-radius: 10px;
                padding: 10px;
                font-size: 15px;
            }
            QLineEdit {
                background-color: #0b1020;
                color: white;
                border: 1px solid #2f81f7;
                border-radius: 10px;
                padding: 10px;
                font-size: 15px;
            }
            QPushButton {
                background-color: #0969da;
                color: white;
                border-radius: 10px;
                padding: 10px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1f6feb; }
            QFrame {
                background-color: #0b1020;
                border: 1px solid #1f6feb;
                border-radius: 12px;
            }
        """)

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        title = QLabel("JARVIS OS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 44px; font-weight: bold; color: #58a6ff;")
        main_layout.addWidget(title)

        self.system_status = QLabel(self.monitor.get_status_text())
        self.system_status.setAlignment(Qt.AlignCenter)
        self.system_status.setStyleSheet("font-size: 14px; color: #7ee787;")
        main_layout.addWidget(self.system_status)

        voice_text = "ONLINE" if self.voice_online else "OFFLINE"
        self.status = QLabel(
            f"● Brain: ONLINE   ● Vision: READY   ● Memory: ACTIVE   ● Voice: {voice_text}   ● Trading: DEMO LATER"
        )
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-size: 14px; color: #7ee787;")
        main_layout.addWidget(self.status)

        body = QHBoxLayout()
        main_layout.addLayout(body)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        self.modules = QLabel()
        self.modules.setStyleSheet("font-size: 16px;")
        left_layout.addWidget(self.modules)
        body.addWidget(left_panel, 1)

        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.append("Jarvis: Witaj Kacper. Dashboard systemowy jest online.")
        self.chat.append("Jarvis: Proste polecenia wykonuję od razu. Tylko naprawdę ryzykowne akcje wymagają potwierdzenia.")
        self.chat.append("Jarvis: Monitoruję CPU, RAM, dysk i czas.")

        if self.voice_online:
            self.chat.append("Jarvis: Voice ONLINE. Powiedz polecenie lub wpisz je ręcznie.")
        else:
            self.chat.append("Jarvis: Voice OFFLINE. Mikrofon wyłączony, wpisz polecenie ręcznie.")

        center_layout.addWidget(self.chat)

        input_layout = QHBoxLayout()

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Napisz polecenie...")
        self.entry.returnPressed.connect(self.handle_input)
        input_layout.addWidget(self.entry)

        self.button = QPushButton("WYŚLIJ")
        self.button.clicked.connect(self.handle_input)
        input_layout.addWidget(self.button)

        center_layout.addLayout(input_layout)
        body.addWidget(center_panel, 3)

        self.voice_text_signal.connect(self.handle_voice_text)

        if self.voice is not None:
            self.voice.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_system_status)
        self.timer.start(1000)

        self.update_system_status()

    def update_system_status(self):
        text = self.monitor.get_status_text()
        self.system_status.setText(text)

        voice_text = "ONLINE" if self.voice_online else "OFFLINE"

        background_text = "OFFLINE"
        try:
            background_status = self.brain.background_status()
            if background_status.get("running", False):
                background_text = "RUNNING"
            elif background_status.get("status") == "STOPPED":
                background_text = "READY"
        except Exception:
            background_text = "OFFLINE"

        self.modules.setText(
            "MODUŁY\n\n"
            "🧠 Brain: ONLINE\n"
            "👁 Vision: READY\n"
            "🖱 Desktop: ONLINE\n"
            "💾 Memory: ACTIVE\n"
            f"🎤 Voice: {voice_text}\n"
            f"⚙ Background AutoDev: {background_text}\n"
            "📈 Trading: OFFLINE\n\n"
            "SYSTEM\n\n"
            f"CPU: {self.monitor.get_cpu_usage()}\n"
            f"RAM: {self.monitor.get_ram_usage()}\n"
            f"DYSK: {self.monitor.get_disk_usage()}\n"
            f"CZAS PRACY: {self.monitor.get_uptime()}"
        )

    def handle_input(self):
        text = self.entry.text().strip()
        if not text:
            return

        self.entry.clear()
        self.process_command(text, source="Ty")

    def handle_voice_text_safe(self, text: str):
        self.voice_text_signal.emit(text)

    def handle_voice_text(self, text: str):
        text = text.strip().lower()
        if not text:
            return

        self.process_command(text, source="Ty głosem")

    def say_safe(self, text: str):
        if self.voice is not None:
            try:
                self.voice.say(text)
            except Exception:
                pass

    def is_safe_thought(self, thought: dict) -> bool:
        if thought.get("handler") == "background_autodev":
            return True

        safe_actions = [
            ActionTypes.OPEN_WEBSITE,
            ActionTypes.OPEN_APP,
            ActionTypes.GOOGLE_SEARCH,
            ActionTypes.YOUTUBE_SEARCH,
            ActionTypes.TYPE_TEXT,
            ActionTypes.PRESS_ENTER,
            ActionTypes.CLICK,
            ActionTypes.SCREENSHOT,
            ActionTypes.VISION_ANALYZE,
            ActionTypes.VISION_CLICK,
            ActionTypes.YOUTUBE_FIRST_VIDEO,
            ActionTypes.REMEMBER,
            ActionTypes.ADD_TASK,
            ActionTypes.MEMORY_SUMMARY
        ]

        actions = thought.get("actions", [])

        if not actions:
            return False

        for action in actions:
            action_type = action.get("action_type")

            if action_type not in safe_actions:
                return False

        return True

    def process_command(self, text: str, source: str = "Ty"):
        self.chat.append(f"\n{source}: {text}")

        if self.pending_thought is not None:
            self.handle_confirmation(text)
            return

        if text.lower().strip() in ["jarvis", "hej jarvis", "cześć jarvis"]:
            self.chat.append("Jarvis: Słucham.")
            self.say_safe("Słucham")
            return

        thought = self.brain.think(text)

        self.chat.append("Jarvis: Plan działania:")
        for i, step in enumerate(thought["plan"], start=1):
            self.chat.append(f"{i}. {step}")

        if not thought["can_execute"]:
            self.chat.append("Jarvis: Nie wykonuję tej akcji.")
            return

        if self.is_safe_thought(thought):
            response = self.brain.execute(thought)
            self.chat.append(f"Jarvis: {response}")
            self.say_safe(response)
            return

        self.pending_thought = thought
        self.chat.append("Jarvis: Ta akcja może być ważna. Wpisz TAK, żeby wykonać, albo NIE, żeby anulować.")
        self.say_safe("Potwierdź wykonanie.")

    def handle_confirmation(self, answer: str):
        answer = answer.lower().strip()

        if answer in ["tak", "ta", "wykonaj", "potwierdzam", "ok", "okej"]:
            response = self.brain.execute(self.pending_thought)
            self.chat.append(f"Jarvis: {response}")
            self.say_safe(response)
        else:
            self.chat.append("Jarvis: Anulowano.")
            self.say_safe("Anulowano")

        self.pending_thought = None

    def closeEvent(self, event):
        try:
            if self.voice is not None:
                self.voice.stop()
        except Exception:
            pass

        try:
            self.brain.shutdown()
        except Exception:
            pass

        event.accept()
