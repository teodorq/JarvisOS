from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app.business.business_config import BusinessConfigStore
from app.cloud.environment import load_cloud_environment
from app.core.project_paths import resolve_project_root
from app.voice.environment import load_voice_environment


def main() -> int:
    project_root = resolve_project_root()
    load_cloud_environment(project_root)
    load_voice_environment(project_root)
    from app.gui.main_window import MainWindow

    config = BusinessConfigStore(project_root).ensure()

    app = QApplication(sys.argv)
    app.setApplicationName(str(config["product_name"]))
    app.setApplicationDisplayName(str(config["product_name"]))
    app.setOrganizationName(str(config["organization"]))

    icon_path = project_root / "JARVIS_OS.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    splash_path = project_root / "JARVIS_OS.png"
    pixmap = QPixmap(str(splash_path))
    if not pixmap.isNull():
        pixmap = pixmap.scaled(
            520,
            520,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        splash = QSplashScreen(pixmap)
        splash.setWindowFlag(Qt.FramelessWindowHint)
        splash.show()
        app.processEvents()
    else:
        splash = None

    window = MainWindow()
    window.show_start_mode()
    if splash is not None:
        QTimer.singleShot(100, splash.close)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
