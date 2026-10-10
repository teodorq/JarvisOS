from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.request

from app.core.performance_profile import load_performance_profile


_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$")
_TRUE = {"1", "true", "yes", "on"}


class LocalChatModel:
    """Small Ollama chat client fixed to localhost and without tool access."""

    URL = "http://127.0.0.1:11434/api/chat"

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        profile_name = (
            load_performance_profile(project_root).name
            if project_root is not None
            else "balanced"
        )
        low_resource = profile_name == "low_resource"
        default_threads = 4 if low_resource else 6
        default_context = 1536 if low_resource else 2048
        selected = str(
            model or os.getenv("JARVIS_OS_CHAT_MODEL", "gemma3:4b")
        ).strip()
        self.model = (
            selected if _MODEL_NAME.fullmatch(selected) else "gemma3:4b"
        )
        self.timeout = _bounded_timeout(
            timeout if timeout is not None else os.getenv("JARVIS_OS_CHAT_TIMEOUT_SECONDS", "50")
        )
        self.cpu_threads = _bounded_int(
            os.getenv("JARVIS_OS_CHAT_CPU_THREADS", str(default_threads)),
            minimum=1,
            maximum=16,
            fallback=default_threads,
        )
        self.gpu_layers = _bounded_int(
            os.getenv("JARVIS_OS_CHAT_GPU_LAYERS", "0"), minimum=0, maximum=999, fallback=0
        )
        self.response_tokens = _bounded_int(
            os.getenv("JARVIS_OS_CHAT_RESPONSE_TOKENS", "220"),
            minimum=48,
            maximum=512,
            fallback=220,
        )
        self.context_tokens = _bounded_int(
            os.getenv("JARVIS_OS_CHAT_CONTEXT_TOKENS", str(default_context)),
            minimum=1024,
            maximum=4096,
            fallback=default_context,
        )
        self.performance_profile = profile_name
        self.keep_alive = "90s" if low_resource else "5m"
        flag = os.getenv("JARVIS_OS_LOCAL_CHAT_ENABLED", "true")
        self.enabled = str(flag).strip().casefold() in _TRUE

    def set_response_budget(self, tokens: object) -> None:
        self.response_tokens = _bounded_int(
            tokens, minimum=48, maximum=512, fallback=220,
        )

    def reply(self, messages: list[dict[str, str]], *, system: str) -> str:
        if not self.enabled:
            return ""
        safe_messages = [
            {"role": item["role"], "content": str(item["content"])[:2_000]}
            for item in messages[-15:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "messages": [{"role": "system", "content": system[:4_000]}, *safe_messages],
            "options": {
                "temperature": 0.45,
                "top_p": 0.85,
                "repeat_penalty": 1.1,
                "num_predict": self.response_tokens,
                "num_ctx": self.context_tokens,
                "num_thread": self.cpu_threads,
                "num_gpu": self.gpu_layers,
            },
        }
        request = urllib.request.Request(
            self.URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if getattr(response, "status", 200) != 200:
                    return ""
                result: Any = json.loads(response.read(1_000_000).decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError, TimeoutError):
            return ""
        message = dict(result.get("message", {}) or {}) if isinstance(result, dict) else {}
        text = str(message.get("content", "") or "").strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S).strip()
        return text[:3_200]

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "backend": "OLLAMA_LOCAL",
            "model": self.model,
            "remote": False,
            "tools": False,
            "timeout_seconds": self.timeout,
            "response_tokens": self.response_tokens,
            "context_tokens": self.context_tokens,
            "processor": "CPU" if self.gpu_layers == 0 else "GPU",
            "performance_profile": self.performance_profile,
            "keep_alive": self.keep_alive,
        }


def _bounded_timeout(value: object) -> float:
    try:
        return min(60.0, max(5.0, float(value)))
    except (TypeError, ValueError):
        return 50.0


def _bounded_int(
    value: object, *, minimum: int, maximum: int, fallback: int,
) -> int:
    try:
        return min(maximum, max(minimum, int(value)))
    except (TypeError, ValueError):
        return fallback


__all__ = ["LocalChatModel"]
