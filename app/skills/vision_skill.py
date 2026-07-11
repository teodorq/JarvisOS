from app.ai.actions import ActionTypes
from app.skills.base_skill import BaseSkill
from app.vision.screen import ScreenVision
from app.vision.vision_ai import VisionAI
from app.vision.vision_agent import VisionAgent
from app.vision2.vision_brain import VisionBrain


class VisionSkill(BaseSkill):

    name = "vision"

    def __init__(self):
        self.vision = ScreenVision()
        self.vision_ai = VisionAI()
        self.vision_agent = VisionAgent()
        self.vision_brain = VisionBrain(self.vision)

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            ActionTypes.SCREENSHOT,
            ActionTypes.VISION_ANALYZE,
            ActionTypes.VISION_CLICK,
            ActionTypes.YOUTUBE_FIRST_VIDEO
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")

        if action_type == ActionTypes.SCREENSHOT:
            path = self.vision.take_screenshot()
            return f"Screenshot zapisany:\n{path}"

        if action_type == ActionTypes.VISION_ANALYZE:
            return self.execute_vision_analyze()

        if action_type == ActionTypes.YOUTUBE_FIRST_VIDEO:
            return self.execute_vision_click({"target": "pierwszy film"})

        if action_type == ActionTypes.VISION_CLICK:
            return self.execute_vision_click(action)

        return None

    def execute_vision_analyze(self):
        result = self.vision_brain.describe_screen()

        screen = result.get("screen", {})
        decision = result.get("decision", {})
        summary = result.get("summary", "")
        elements = result.get("elements", [])
        elements_count = result.get("elements_count", 0)
        screen_text = screen.get("screen_text", "")

        lines = [
            "VisionBrain:",
            f"Aplikacja: {screen.get('application')}",
            f"Strona: {screen.get('page')}",
            f"Okno: {screen.get('window_title')}",
            f"Opis: {summary}",
            f"Liczba elementów GUI: {elements_count}",
            f"Decyzja: {decision.get('reason')}",
            f"Pytać użytkownika: {decision.get('ask_user')}",
        ]

        if screen_text:
            short_text = screen_text.strip()
            if len(short_text) > 700:
                short_text = short_text[:700] + "..."

            lines.append("")
            lines.append("Tekst z ekranu OCR:")
            lines.append(short_text)

        if elements:
            lines.append("")
            lines.append("Najważniejsze elementy:")

            for element in elements[:8]:
                lines.append(
                    f"- {element.get('type', 'unknown')}: "
                    f"{element.get('text', '')} "
                    f"({element.get('x', 0)}, {element.get('y', 0)})"
                )

        return "\n".join(lines)

    def execute_vision_click(self, action: dict):
        target = action.get("target", "")

        vision_result = self.vision_brain.find_element(target)
        gui_result = vision_result.get("result", {})

        if gui_result.get("found") and gui_result.get("element"):
            element = gui_result["element"]

            x = int(element.get("x", 0))
            y = int(element.get("y", 0))

            self.vision_agent.screen.take_screenshot()
            self.vision_agent.screen.get_mouse_position()

            from app.desktop.controller import DesktopController
            desktop = DesktopController()
            desktop.move_mouse(x, y)
            desktop.click()

            return f'Kliknięto "{target}" przez VisionSkill.'

        result = self.vision_agent.find_element(target)

        if not result.get("found"):
            return result.get("description", "Nie znaleziono elementu.")

        x = int(result.get("x", 0))
        y = int(result.get("y", 0))

        from app.desktop.controller import DesktopController
        desktop = DesktopController()
        desktop.move_mouse(x, y)
        desktop.click()

        return f'Kliknięto "{target}".'
