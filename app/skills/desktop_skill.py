from app.ai.actions import ActionTypes
from app.agent.desktop_brain import DesktopBrain
from app.skills.base_skill import BaseSkill


class DesktopSkill(BaseSkill):

    name = "desktop"

    def __init__(self):
        self.desktop = DesktopBrain()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            ActionTypes.TYPE_TEXT,
            ActionTypes.PRESS_ENTER,
            ActionTypes.CLICK,
            "DOUBLE_CLICK",
            "RIGHT_CLICK",
            "SCROLL_DOWN",
            "SCROLL_UP",
            "COPY",
            "PASTE",
            "CUT",
            "SELECT_ALL",
            "CLOSE_WINDOW",
            "SWITCH_WINDOW",
            "MINIMIZE_WINDOW",
            "MAXIMIZE_WINDOW",
            "OPEN_START_MENU",
            "DESKTOP_HISTORY"
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")

        if action_type == ActionTypes.TYPE_TEXT:
            return self.desktop.execute("type_text", action.get("text", ""))

        if action_type == ActionTypes.PRESS_ENTER:
            return self.desktop.execute("press", "enter")

        if action_type == ActionTypes.CLICK:
            return self.desktop.execute("click")

        if action_type == "DOUBLE_CLICK":
            return self.desktop.execute("double_click")

        if action_type == "RIGHT_CLICK":
            return self.desktop.execute("right_click")

        if action_type == "SCROLL_DOWN":
            return self.desktop.execute("scroll_down")

        if action_type == "SCROLL_UP":
            return self.desktop.execute("scroll_up")

        if action_type == "COPY":
            return self.desktop.execute("copy")

        if action_type == "PASTE":
            return self.desktop.execute("paste")

        if action_type == "CUT":
            return self.desktop.execute("cut")

        if action_type == "SELECT_ALL":
            return self.desktop.execute("select_all")

        if action_type == "CLOSE_WINDOW":
            return self.desktop.execute("close_window")

        if action_type == "SWITCH_WINDOW":
            return self.desktop.execute("switch_window")

        if action_type == "MINIMIZE_WINDOW":
            return self.desktop.execute("minimize_window")

        if action_type == "MAXIMIZE_WINDOW":
            return self.desktop.execute("maximize_window")

        if action_type == "OPEN_START_MENU":
            return self.desktop.execute("open_start_menu")

        if action_type == "DESKTOP_HISTORY":
            return self.desktop.history_summary()

        return None