"""B96-B105 personal assistant and intelligence runtime."""

__all__ = ["PersonalAssistantController"]


def __getattr__(name: str):
    if name == "PersonalAssistantController":
        from app.assistant.controller import PersonalAssistantController
        return PersonalAssistantController
    raise AttributeError(name)
