from app.vision.gui_detector import GuiDetector
from app.vision2.screen_analyzer import ScreenAnalyzer
from app.vision2.vision_memory import VisionMemory
from app.vision2.world_model import WorldModel


class VisionBrain:

    def __init__(self, screen_vision):
        self.screen_analyzer = ScreenAnalyzer(screen_vision)
        self.gui_detector = GuiDetector()
        self.memory = VisionMemory()
        self.world_model = WorldModel()

    def analyze(self) -> dict:
        screen = self.screen_analyzer.analyze()
        world = self.world_model.build(screen)

        self.memory.remember(screen)

        return {
            "screen": screen,
            "world": world,
            "gui": None,
            "memory": self.memory.summary(),
            "decision": self._make_decision(screen),
            "source": "screen_analyzer"
        }

    def describe_screen(self) -> dict:
        screen = self.screen_analyzer.analyze()
        world = self.world_model.build(screen)
        gui = self.gui_detector.scan()

        self.memory.remember(screen)
        self.memory.remember_gui(gui)

        elements = gui.get("elements", [])

        for element in elements:
            self._cache_element_aliases(element)

        return {
            "screen": screen,
            "world": world,
            "summary": gui.get("summary", ""),
            "elements_count": len(elements),
            "elements": elements,
            "memory": self.memory.summary(),
            "decision": self._make_decision(screen),
            "source": "gui_detector"
        }

    def scan_gui(self) -> dict:
        screen = self.screen_analyzer.analyze()
        world = self.world_model.build(screen)
        gui = self.gui_detector.scan()

        self.memory.remember(screen)
        self.memory.remember_gui(gui)

        elements = gui.get("elements", [])

        for element in elements:
            self._cache_element_aliases(element)

        return {
            "screen": screen,
            "world": world,
            "gui": gui,
            "memory": self.memory.summary(),
            "decision": self._make_decision(screen),
            "source": "gui_detector"
        }

    def find_element(self, target: str) -> dict:
        target = (target or "").strip()
        screen = self.screen_analyzer.analyze()
        world = self.world_model.build(screen)

        self.memory.remember(screen)

        cached_element = self.memory.get_element(target)

        if cached_element and not self._screen_changed(screen):
            return {
                "screen": screen,
                "world": world,
                "target": target,
                "result": {
                    "found": True,
                    "element": cached_element,
                    "score": 999,
                    "summary": "Element znaleziony w VisionMemory cache.",
                    "screenshot": ""
                },
                "memory": self.memory.summary(),
                "decision": self._make_decision(screen),
                "source": "vision_memory_cache"
            }

        gui_result = self.gui_detector.find(target)

        if gui_result.get("found") and gui_result.get("element"):
            self._cache_element_aliases(gui_result["element"])
            self.memory.remember_element(target, gui_result["element"])

        return {
            "screen": screen,
            "world": world,
            "target": target,
            "result": gui_result,
            "memory": self.memory.summary(),
            "decision": self._make_decision(screen),
            "source": "gui_detector"
        }

    def should_ask_user(self) -> bool:
        screen = self.screen_analyzer.analyze()
        self.memory.remember(screen)

        decision = self._make_decision(screen)
        return decision.get("ask_user", False)

    def _cache_element_aliases(self, element: dict):
        if not element:
            return

        text = str(element.get("text", "")).strip()
        element_type = str(element.get("type", "")).strip()

        if text:
            self.memory.remember_element(text, element)

        if element_type:
            self.memory.remember_element(element_type, element)

        if "pierwszy film" in text.lower():
            self.memory.remember_element("pierwszy film", element)
            self.memory.remember_element("film", element)
            self.memory.remember_element("video", element)

        if element_type.lower() in ["video", "thumbnail", "title"]:
            self.memory.remember_element("pierwszy film", element)

        if element_type.lower() in ["input", "textbox", "search"]:
            self.memory.remember_element("pole wyszukiwania", element)
            self.memory.remember_element("szukaj", element)

    def _screen_changed(self, current_screen: dict) -> bool:
        previous = self.memory.previous()

        if not previous:
            return True

        if previous.get("window_title", "") != current_screen.get("window_title", ""):
            return True

        change = current_screen.get("change", {})
        change_type = change.get("change_type", "none")

        if change_type in ["window_changed", "text_changed"]:
            return True

        return False

    def _make_decision(self, screen: dict) -> dict:
        change = screen.get("change", {})
        change_type = change.get("change_type", "none")
        importance = change.get("importance", "low")
        application = screen.get("application", "unknown")
        page = screen.get("page", "unknown")

        if change_type == "mouse_moved":
            return {
                "ask_user": False,
                "reason": "To tylko ruch myszy.",
                "priority": "low"
            }

        if change_type == "initial":
            return {
                "ask_user": False,
                "reason": "Pierwszy odczyt ekranu, nie trzeba pytać użytkownika.",
                "priority": "low"
            }

        if change_type == "window_changed":
            return {
                "ask_user": True,
                "reason": "Zmieniło się aktywne okno.",
                "priority": "high"
            }

        if importance == "medium":
            return {
                "ask_user": False,
                "reason": "Zmiana średniej ważności, można kontynuować bez pytania.",
                "priority": "medium"
            }

        return {
            "ask_user": False,
            "reason": f"Brak potrzeby pytania użytkownika. App={application}, page={page}.",
            "priority": "low"
        }