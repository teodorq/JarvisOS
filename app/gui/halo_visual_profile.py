from __future__ import annotations


COLORS = {
    "idle": "#43B9FF",
    "listening": "#4DEBFF",
    "thinking": "#669DFF",
    "acting": "#53CCFF",
    "speaking": "#B47CFF",
    "success": "#53E6BD",
    "brief": "#43B9FF",
    "important": "#FFB454",
    "warning": "#FF9D57",
    "error": "#FF6678",
}
SPEEDS = {
    "idle": 0.42, "listening": 0.92, "thinking": 1.28,
    "acting": 1.72, "speaking": 0.82, "success": 0.58,
    "brief": 0.48, "important": 0.74, "warning": 1.05, "error": 0.45,
}
ACCESSIBLE = {
    "idle": "Jarvis jest gotowy",
    "listening": "Jarvis słucha",
    "thinking": "Jarvis analizuje",
    "acting": "Jarvis wykonuje zadanie",
    "speaking": "Jarvis odpowiada",
    "success": "Jarvis zakończył zadanie",
    "brief": "Jarvis pokazuje brief dnia",
    "important": "Jarvis pokazuje ważną informację",
    "warning": "Jarvis czeka na decyzję",
    "error": "Jarvis wymaga uwagi",
}
INTENSITY = {
    "idle": 0.8, "listening": 1.0, "thinking": 0.94,
    "acting": 1.0, "speaking": 0.96, "success": 0.88,
    "brief": 0.8, "important": 0.92, "warning": 0.96, "error": 0.84,
}


__all__ = ["ACCESSIBLE", "COLORS", "INTENSITY", "SPEEDS"]
