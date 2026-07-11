import pygetwindow as gw


class WindowScanner:

    def get_open_windows(self):
        windows = []

        for window in gw.getAllWindows():
            try:
                title = (window.title or "").strip()

                if not title:
                    continue

                left = int(window.left)
                top = int(window.top)
                width = int(window.width)
                height = int(window.height)

                if width <= 0 or height <= 0:
                    continue

                windows.append({
                    "title": title,
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "right": left + width,
                    "bottom": top + height,
                    "active": bool(window.isActive),
                    "minimized": bool(window.isMinimized),
                    "maximized": bool(window.isMaximized)
                })

            except Exception:
                pass

        return windows

    def get_active_window(self):
        try:
            window = gw.getActiveWindow()

            if window is None:
                return None

            title = (window.title or "").strip()
            left = int(window.left)
            top = int(window.top)
            width = int(window.width)
            height = int(window.height)

            if width <= 0 or height <= 0:
                return None

            return {
                "title": title,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "active": True,
                "minimized": bool(window.isMinimized),
                "maximized": bool(window.isMaximized)
            }

        except Exception:
            return None

    def find_window(self, keyword: str):
        keyword = (keyword or "").lower().strip()

        if not keyword:
            return None

        for window in self.get_open_windows():
            title = window.get("title", "").lower()

            if keyword in title:
                return window

        return None

    def find_browser_window(self):
        keywords = [
            "youtube",
            "opera",
            "chrome",
            "edge",
            "firefox",
            "chatgpt",
            "google"
        ]

        for keyword in keywords:
            window = self.find_window(keyword)
            if window:
                return window

        return None

    def describe_windows(self):
        windows = self.get_open_windows()

        if not windows:
            return "Nie widzę żadnych okien."

        text = "Widzę następujące okna:\n\n"

        for i, window in enumerate(windows, start=1):
            active = " [AKTYWNE]" if window.get("active") else ""

            text += (
                f"{i}. {window.get('title')}{active}\n"
                f"   x={window.get('left')}  y={window.get('top')}\n"
                f"   {window.get('width')}x{window.get('height')}\n\n"
            )

        return text