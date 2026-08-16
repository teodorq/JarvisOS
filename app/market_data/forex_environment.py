"""Allowlisted loader for ignored local Forex data credentials."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re


MAX_FOREX_ENV_BYTES = 16_384
ALLOWED_FOREX_ENVIRONMENT_KEYS = frozenset(
    {
        "JARVIS_OS_FOREX_DATA_ENABLED",
        "JARVIS_OS_FOREX_PRIMARY_PROVIDER",
        "JARVIS_OS_MT5_SYMBOL_SUFFIX",
        "JARVIS_OS_OANDA_PRACTICE_ACCOUNT_ID",
        "JARVIS_OS_OANDA_PRACTICE_TOKEN",
        "JARVIS_OS_TWELVE_DATA_API_KEY",
        "JARVIS_OS_FMP_API_KEY",
    }
)


def load_forex_environment(project_root: str | Path) -> tuple[str, ...]:
    """Load config/forex.env without overriding process-level settings."""

    path = Path(project_root) / "config" / "forex.env"
    try:
        if not path.is_file() or path.stat().st_size > MAX_FOREX_ENV_BYTES:
            return ()
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ()
    loaded: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key not in ALLOWED_FOREX_ENVIRONMENT_KEYS or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not value or "\x00" in value or len(value) > 4096:
            continue
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


@dataclass(frozen=True, slots=True)
class ForexDataSettings:
    enabled: bool
    primary_provider: str = "MT5_DEMO"
    mt5_symbol_suffix: str = ""
    oanda_practice_account_id: str = field(default="", repr=False)
    oanda_practice_token: str = field(default="", repr=False)
    twelve_data_api_key: str = field(default="", repr=False)
    fmp_api_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        provider = str(self.primary_provider or "").strip().upper()
        if provider not in {"MT5_DEMO", "OANDA_PRACTICE"}:
            raise ValueError("unsupported Forex primary provider")
        suffix = str(self.mt5_symbol_suffix or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{0,12}", suffix):
            raise ValueError("invalid MT5 symbol suffix")
        object.__setattr__(self, "primary_provider", provider)
        object.__setattr__(self, "mt5_symbol_suffix", suffix)

    @classmethod
    def from_environment(cls) -> "ForexDataSettings":
        return cls(
            enabled=os.getenv("JARVIS_OS_FOREX_DATA_ENABLED", "").strip().lower()
            == "true",
            primary_provider=os.getenv("JARVIS_OS_FOREX_PRIMARY_PROVIDER", "MT5_DEMO"),
            mt5_symbol_suffix=os.getenv("JARVIS_OS_MT5_SYMBOL_SUFFIX", ""),
            oanda_practice_account_id=os.getenv(
                "JARVIS_OS_OANDA_PRACTICE_ACCOUNT_ID", ""
            ).strip(),
            oanda_practice_token=os.getenv(
                "JARVIS_OS_OANDA_PRACTICE_TOKEN", ""
            ).strip(),
            twelve_data_api_key=os.getenv(
                "JARVIS_OS_TWELVE_DATA_API_KEY", ""
            ).strip(),
            fmp_api_key=os.getenv("JARVIS_OS_FMP_API_KEY", "").strip(),
        )

    @property
    def oanda_ready(self) -> bool:
        return bool(
            self.enabled
            and self.oanda_practice_account_id
            and self.oanda_practice_token
        )

    @property
    def second_source_ready(self) -> bool:
        return bool(self.enabled and self.twelve_data_api_key)

    @property
    def calendar_ready(self) -> bool:
        return bool(self.enabled and self.fmp_api_key)

    @property
    def primary_ready(self) -> bool:
        if self.primary_provider == "MT5_DEMO":
            return self.enabled
        return self.oanda_ready

    def readiness(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "primary_provider": self.primary_provider,
            "mt5_demo": bool(self.enabled and self.primary_provider == "MT5_DEMO"),
            "oanda_practice": self.oanda_ready,
            "independent_second_source": self.second_source_ready,
            "nbp_pln_reference": self.enabled,
            "economic_calendar": self.calendar_ready,
            "complete": bool(
                self.primary_ready
                and self.second_source_ready
                and self.calendar_ready
            ),
        }


__all__ = [
    "ALLOWED_FOREX_ENVIRONMENT_KEYS",
    "ForexDataSettings",
    "MAX_FOREX_ENV_BYTES",
    "load_forex_environment",
]
