class WorldModel:

    def build(self, screen: dict) -> dict:

        app = screen.get("application", "unknown")
        page = screen.get("page", "unknown")
        window = screen.get("window_title", "")
        text = screen.get("screen_text", "").lower()

        state = {
            "application": app,
            "page": page,
            "window": window,
            "activity": "unknown",
            "website": None,
            "video_visible": False,
            "search_visible": False,
            "logged_in": False
        }

        if "youtube" in page or "youtube" in window.lower():
            state["website"] = "youtube"

            if "szukaj" in text or "search" in text:
                state["search_visible"] = True

            if (
                "wyświetleń" in text
                or "views" in text
                or "min temu" in text
                or "godz." in text
                or "film" in text
            ):
                state["video_visible"] = True

            if state["video_visible"]:
                state["activity"] = "watching_youtube"

        elif "google" in page:
            state["website"] = "google"
            state["activity"] = "searching"

        elif "chatgpt" in page:
            state["website"] = "chatgpt"
            state["activity"] = "chatting"

        return state