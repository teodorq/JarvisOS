from app.vision.ocr import OCR
from app.vision.window_scanner import WindowScanner
from app.vision2.vision2 import Vision2


class ScreenAnalyzer:

    def __init__(self, screen_vision):
        self.vision = Vision2(screen_vision)
        self.window_scanner = WindowScanner()
        self.ocr = OCR()

    def analyze(self):

        result = self.vision.analyze_screen()

        state = result["state"]

        active_window = self.window_scanner.get_active_window()
        windows = self.window_scanner.get_open_windows()

        try:
            ocr = self.ocr.read_screen()
            screen_text = ocr.get("text", "")
        except Exception:
            screen_text = ""

        return {
            "window_title": state.window_title,
            "application": state.app_name,
            "page": state.page_context,

            "screen_width": state.screen_width,
            "screen_height": state.screen_height,

            "mouse_x": state.mouse_x,
            "mouse_y": state.mouse_y,

            "change": result["change"],

            "active_window": active_window,
            "windows": windows,

            "screen_text": screen_text
        }