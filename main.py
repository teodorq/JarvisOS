import sys
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer

from app.gui.main_window import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)

    pixmap = QPixmap("JARVIS_OS.png")
    pixmap = pixmap.scaled(
        520,
        520,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
    )

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.FramelessWindowHint)
    splash.show()
    app.processEvents()

    window = MainWindow()

    QTimer.singleShot(1800, splash.close)
    QTimer.singleShot(1800, window.show)

    sys.exit(app.exec())