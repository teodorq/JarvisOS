from dataclasses import dataclass
from typing import Optional


@dataclass
class ScreenState:
    window_title: str = ""
    app_name: str = "unknown"
    page_context: str = "unknown"
    screenshot_path: Optional[str] = None
    raw_text: str = ""
    timestamp: float = 0.0
    screen_width: int = 0
    screen_height: int = 0
    mouse_x: int = 0
    mouse_y: int = 0