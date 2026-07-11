import pygetwindow as gw


class WindowManager:

    def list_windows(self):
        windows = []

        for window in gw.getAllWindows():
            title = (window.title or "").strip()

            if not title:
                continue

            windows.append({
                "title": title,
                "left": window.left,
                "top": window.top,
                "width": window.width,
                "height": window.height,
                "active": window.isActive,
                "minimized": window.isMinimized,
                "maximized": window.isMaximized
            })

        return windows

    def active_window(self):
        window = gw.getActiveWindow()

        if window is None:
            return None

        return {
            "title": window.title,
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
            "active": True
        }

    def find_window(self, name: str):
        name = name.lower().strip()

        for window in gw.getAllWindows():
            title = (window.title or "").lower()

            if name in title:
                return window

        return None

    def focus_window(self, name: str):
        window = self.find_window(name)

        if window is None:
            return f"Nie znaleziono okna: {name}"

        window.activate()
        return f"Aktywowano okno: {window.title}"

    def close_window(self, name: str):
        window = self.find_window(name)

        if window is None:
            return f"Nie znaleziono okna: {name}"

        window.close()
        return f"Zamknięto okno: {window.title}"

    def summary(self):
        windows = self.list_windows()

        if not windows:
            return "Brak widocznych okien."

        lines = ["WINDOW MANAGER"]

        for window in windows[:15]:
            active = " [AKTYWNE]" if window["active"] else ""
            lines.append(
                f"- {window['title']}{active} "
                f"({window['left']}, {window['top']}) "
                f"{window['width']}x{window['height']}"
            )

        return "\n".join(lines)