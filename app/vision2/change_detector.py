from typing import Optional

from app.vision2.screen_state import ScreenState


class ChangeDetector:

    def __init__(self):
        self.previous_state: Optional[ScreenState] = None

    def analyze(self, current_state: ScreenState) -> dict:
        if self.previous_state is None:
            self.previous_state = current_state
            return {
                "changed": True,
                "change_type": "initial",
                "importance": "initial",
                "reason": "Pierwszy odczyt ekranu."
            }

        previous = self.previous_state
        self.previous_state = current_state

        if previous.window_title != current_state.window_title:
            return {
                "changed": True,
                "change_type": "window_changed",
                "importance": "high",
                "reason": "Zmieniło się aktywne okno."
            }

        mouse_moved = (
            previous.mouse_x != current_state.mouse_x
            or previous.mouse_y != current_state.mouse_y
        )

        if mouse_moved:
            return {
                "changed": True,
                "change_type": "mouse_moved",
                "importance": "low",
                "reason": "Poruszył się kursor myszy."
            }

        if previous.raw_text != current_state.raw_text:
            return {
                "changed": True,
                "change_type": "text_changed",
                "importance": "medium",
                "reason": "Zmieniła się treść na ekranie."
            }

        return {
            "changed": False,
            "change_type": "none",
            "importance": "low",
            "reason": "Brak istotnych zmian."
        }