from app.assistant.conversation_preferences import (
    load_conversation_preferences,
    reset_conversation_preferences,
    save_conversation_preferences,
)


def test_conversation_preferences_are_shared_and_hardened(tmp_path) -> None:
    assert load_conversation_preferences(tmp_path) == {
        "style": "natural",
        "question_mode": "balanced",
    }

    saved = save_conversation_preferences(
        tmp_path,
        style="detailed",
        question_mode="engaged",
    )
    assert saved == {"style": "detailed", "question_mode": "engaged"}
    assert load_conversation_preferences(tmp_path) == saved

    hardened = save_conversation_preferences(
        tmp_path,
        style="unsafe",
        question_mode="always",
    )
    assert hardened == {"style": "natural", "question_mode": "balanced"}

    assert reset_conversation_preferences(tmp_path) == {
        "style": "natural",
        "question_mode": "balanced",
    }
