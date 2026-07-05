from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer

from app.ai.brain import Brain
from app.system.monitor import SystemMonitor


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.brain = Brain()
        self.monitor = SystemMonitor()
        self.pending_thought = None

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

        status = QLabel("● Brain: ONLINE   ● Vision: READY   ● Memory: ACTIVE   ● Trading: DEMO LATER")
        status.setAlignment(Qt.AlignCenter)
        status.setStyleSheet("font-size: 14px; color: #7ee787;")
        main_layout.addWidget(status)

        body = QHBoxLayout()
        main_layout.addLayout(body)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        self.modules = QLabel(
            "MODUŁY\n\n"
            "🧠 Brain: ONLINE\n"
            "👁 Vision: READY\n"
            "🖱 Desktop: ONLINE\n"
            "💾 Memory: ACTIVE\n"
            "🎤 Voice: OFFLINE\n"
            "📈 Trading: OFFLINE\n\n"
            "SYSTEM\n\n"
            "CPU: --\n"
            "RAM: --\n"
            "DYSK: --\n"
            "CZAS: --"
        )
        self.modules.setStyleSheet("font-size: 16px;")
        left_layout.addWidget(self.modules)
        body.addWidget(left_panel, 1)

        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.append("Jarvis: Witaj Kacper. Dashboard systemowy jest online.")
        self.chat.append("Jarvis: Monitoruję CPU, RAM, dysk i czas.")
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

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_system_status)
        self.timer.start(1000)

        self.update_system_status()

    def update_system_status(self):
        text = self.monitor.get_status_text()
        self.system_status.setText(text)

        self.modules.setText(
            "MODUŁY\n\n"
            "🧠 Brain: ONLINE\n"
            "👁 Vision: READY\n"
            "🖱 Desktop: ONLINE\n"
            "💾 Memory: ACTIVE\n"
            "🎤 Voice: OFFLINE\n"
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
        self.chat.append(f"\nTy: {text}")

        if self.pending_thought is not None:
            self.handle_confirmation(text)
            return

        thought = self.brain.think(text)

        self.chat.append("Jarvis: Plan działania:")
        for i, step in enumerate(thought["plan"], start=1):
            self.chat.append(f"{i}. {step}")

        if not thought["can_execute"]:
            self.chat.append("Jarvis: Nie wykonuję tej akcji.")
            return

        self.pending_thought = thought
        self.chat.append("Jarvis: Wpisz TAK, żeby wykonać, albo NIE, żeby anulować.")

    def handle_confirmation(self, answer: str):
        if answer.lower().strip() == "tak":
            response = self.brain.execute(self.pending_thought)
            self.chat.append(f"Jarvis: {response}")
        else:
            self.chat.append("Jarvis: Anulowano.")

        self.pending_thought = None