class VisionMemory:

    def __init__(self, max_items: int = 10):
        self.max_items = max_items

        self.history = []

        self.last_gui = None
        self.last_elements = {}

    def remember(self, screen: dict):
        self.history.append(screen)

        if len(self.history) > self.max_items:
            self.history.pop(0)

    def last(self):
        if not self.history:
            return None

        return self.history[-1]

    def previous(self):
        if len(self.history) < 2:
            return None

        return self.history[-2]

    def remember_gui(self, gui: dict):
        self.last_gui = gui

    def last_gui_scan(self):
        return self.last_gui

    def remember_element(self, name: str, element: dict):
        if not name:
            return

        self.last_elements[name.lower()] = element

    def get_element(self, name: str):
        if not name:
            return None

        return self.last_elements.get(name.lower())

    def clear_elements(self):
        self.last_elements = {}

    def summary(self):
        last = self.last()
        previous = self.previous()

        return {
            "has_memory": last is not None,
            "last_screen": last,
            "previous_screen": previous,
            "history_count": len(self.history),
            "cached_gui": self.last_gui is not None,
            "cached_elements": len(self.last_elements)
        }