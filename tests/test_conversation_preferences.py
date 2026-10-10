from app.assistant.conversation_preferences import (
    load_conversation_preferences,
    reset_conversation_preferences,
    save_conversation_preferences,
)


def test_conversation_preferences_are_shared_and_hardened(tmp_path) -> None:
    assert load_conversation_preferences(tmp_path) == {
        "style": "natural",
        "question_mode": "balanced",
        "memory_depth": 6,
        "context_hours": 1,
    }

    saved = save_conversation_preferences(
        tmp_path,
        style="detailed",
        question_mode="engaged",
        memory_depth=10,
        context_hours=24,
    )
    assert saved == {
        "style": "detailed", "question_mode": "engaged", "memory_depth": 10,
        "context_hours": 24,
    }
    assert load_conversation_preferences(tmp_path) == saved

    hardened = save_conversation_preferences(
        tmp_path,
        style="unsafe",
        question_mode="always",
        memory_depth=99,
        context_hours=99,
    )
    assert hardened == {
        "style": "natural", "question_mode": "balanced", "memory_depth": 6,
        "context_hours": 1,
    }

    assert reset_conversation_preferences(tmp_path) == {
        "style": "natural",
        "question_mode": "balanced",
        "memory_depth": 6,
        "context_hours": 1,
    }
