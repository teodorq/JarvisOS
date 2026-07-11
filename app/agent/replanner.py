from app.ai.actions import ActionTypes


class RePlanner:

    def repair_step(self, step, feedback: dict):
        reason = str(feedback.get("reason", "")).lower()
        next_hint = str(feedback.get("next_hint", "")).lower()

        text = reason + " " + next_hint

        if "nie znaleziono" in text or "nie widzę" in text:
            return self._vision_analyze_step(step)

        if "klik" in text or "click" in text:
            return self._vision_click_step(step)

        if "youtube" in text and "film" in text:
            return self._youtube_first_video_step(step)

        return None

    def _vision_analyze_step(self, step):
        step.action_type = ActionTypes.VISION_ANALYZE
        step.target = ""
        step.text = ""
        step.query = ""
        step.instruction = "Przeanalizować ekran ponownie"
        return step

    def _vision_click_step(self, step):
        if not step.target:
            step.target = step.query or step.text

        step.action_type = ActionTypes.VISION_CLICK
        step.instruction = f"Kliknąć element: {step.target}"
        return step

    def _youtube_first_video_step(self, step):
        step.action_type = ActionTypes.YOUTUBE_FIRST_VIDEO
        step.target = "pierwszy film"
        step.text = ""
        step.query = ""
        step.instruction = "Kliknąć pierwszy film na YouTube"
        return step