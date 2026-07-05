import pygetwindow as gw


class WindowScanner:
    def get_open_windows(self):
        windows = []

        for title in gw.getAllTitles():
            title = title.strip()
            if title:
                windows.append(title)

        return windows

    def describe_windows(self):
        windows = self.get_open_windows()

        if not windows:
            return "Nie widzę żadnych okien."

        text = "Widzę następujące okna:\n\n"

        for i, window in enumerate(windows, start=1):
            text += f"{i}. {window}\n"

        return text