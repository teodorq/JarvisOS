from app.ai.actions import ActionTypes
from app.browser.browser import BrowserAgent
from app.skills.base_skill import BaseSkill


class BrowserSkill(BaseSkill):

    name = "browser"

    def __init__(self):
        self.browser = BrowserAgent()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            ActionTypes.GOOGLE_SEARCH,
            ActionTypes.YOUTUBE_SEARCH
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")

        if action_type == ActionTypes.GOOGLE_SEARCH:
            return self.browser.google_search(action.get("query", ""))

        if action_type == ActionTypes.YOUTUBE_SEARCH:
            return self.browser.youtube_search(action.get("query", ""))

        return None