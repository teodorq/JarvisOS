from __future__ import annotations

from typing import Any


_OWNER_PAGES = {
    "console", "settings", "trust", "platform", "operations", "release",
    "commercial", "assistant", "intelligence", "productivity", "stability",
    "forex", "assistant_v12", "online",
}


def harden_user_preferences(config: dict[str, Any]) -> None:
    ui = dict(config.get("ui", {}) or {})
    page = str(ui.get("start_page", "console")).strip().casefold()[:20]
    mode = str(ui.get("startup_mode", "remember")).strip().casefold()[:20]
    ui["start_page"] = page if page in _OWNER_PAGES else "console"
    ui["startup_mode"] = (
        mode if mode in {"remember", "client", "owner"} else "remember"
    )
    ui["show_quick_actions"] = bool(ui.get("show_quick_actions", True))
    ui["density"] = "comfortable"
    config["ui"] = ui

    performance = dict(config.get("performance", {}) or {})
    profile = str(performance.get("profile", "auto")).strip().casefold()[:24]
    performance["profile"] = (
        profile if profile in {"auto", "balanced", "low_resource"} else "auto"
    )
    config["performance"] = performance

    sound = dict(config.get("sound", {}) or {})
    sound["effects_enabled"] = bool(sound.get("effects_enabled", True))
    config["sound"] = sound


__all__ = ["harden_user_preferences"]
