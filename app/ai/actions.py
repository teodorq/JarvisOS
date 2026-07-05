class ActionTypes:
    OPEN_WEBSITE = "open_website"
    OPEN_APP = "open_app"
    TYPE_TEXT = "type_text"
    CLICK = "click"
    SCREENSHOT = "screenshot"
    REMEMBER = "remember"
    ADD_TASK = "add_task"
    MEMORY_SUMMARY = "memory_summary"

    GOOGLE_SEARCH = "google_search"
    YOUTUBE_SEARCH = "youtube_search"
    OPEN_URL = "open_url"
    PRESS_ENTER = "press_enter"

    VISION_ANALYZE = "vision_analyze"

    UNKNOWN = "unknown"


class Action:
    def __init__(
        self,
        action_type: str,
        target: str = "",
        text: str = "",
        url: str = "",
        query: str = ""
    ):
        self.action_type = action_type
        self.target = target
        self.text = text
        self.url = url
        self.query = query

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "text": self.text,
            "url": self.url,
            "query": self.query
        }