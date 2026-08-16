"""Safe, local-only status summary for optional JARVIS OS integrations."""

from __future__ import annotations

import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from app.integrations.external_services import ExternalIntegrationRegistry


_VOICE_PROVIDERS = {
    "CARTESIA": "CARTESIA",
    "CARTESIA_SONIC": "CARTESIA",
    "CARTESIA_SONIC_3_5": "CARTESIA",
    "ELEVENLABS": "ELEVENLABS",
    "ELEVEN_LABS": "ELEVENLABS",
}
_LOCAL_VOICE_PROVIDERS = {
    "",
    "AUTO",
    "LOCAL",
    "PYTTSX3",
    "SAPI",
    "WINDOWS",
    "WINDOWS_ONECORE",
}
_VOICE_ID = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
_ENDPOINT_ERRORS = {
    "missing_endpoint",
    "invalid_endpoint",
    "https_required",
    "unsafe_endpoint_components",
    "https_port_required",
    "public_dns_host_required",
    "host_not_allowlisted",
    "path_not_allowlisted",
    "unsafe_endpoint_path",
}


def _present(environment: Mapping[str, str], key: str) -> bool:
    return bool(str(environment.get(key, "") or "").strip())


def _safe_https_endpoint(value: object) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
        return (
            parsed.scheme.casefold() == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


class IntegrationStatusService:
    """Describe configuration readiness without network calls or secret output."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self.environment = environment if environment is not None else os.environ

    def status(self) -> dict[str, Any]:
        requested = str(
            self.environment.get("JARVIS_OS_VOICE_PROVIDER", "") or ""
        ).strip().upper().replace("-", "_")
        if requested in _LOCAL_VOICE_PROVIDERS:
            selected_voice = "LOCAL"
            voice_configured = True
        else:
            selected_voice = _VOICE_PROVIDERS.get(requested, "INVALID")
            if selected_voice == "CARTESIA":
                key_name, voice_name = "CARTESIA_API_KEY", "CARTESIA_VOICE_ID"
            elif selected_voice == "ELEVENLABS":
                key_name, voice_name = "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"
            else:
                key_name = voice_name = ""
            voice_id = str(self.environment.get(voice_name, "") or "").strip()
            voice_configured = bool(
                key_name
                and _present(self.environment, key_name)
                and _VOICE_ID.fullmatch(voice_id)
            )

        external_status = ExternalIntegrationRegistry(self.environment).status()
        external = {
            name: {
                "enabled": bool(provider.get("enabled")),
                "ready": bool(provider.get("ready")),
                "mode": str(provider.get("mode", "")),
                "configuration_error": str(
                    provider.get("configuration_error", "") or ""
                ),
            }
            for name, provider in external_status.items()
        }
        return {
            "voice": {
                "selected": selected_voice,
                "configured": voice_configured,
                "local_fallback": True,
            },
            "azure": {
                "planner_configured": bool(
                    _safe_https_endpoint(
                        self.environment.get("JARVIS_OS_CLOUD_URL", "")
                    )
                    and _present(self.environment, "JARVIS_OS_CLOUD_API_TOKEN")
                ),
                "phone_queue_configured": _safe_https_endpoint(
                    self.environment.get("JARVIS_OS_REMOTE_QUEUE_URL", "")
                ),
            },
            "external": external,
            "network_checked": False,
            "secrets_exposed": False,
        }

    snapshot = status

    def format_status(self) -> str:
        status = self.status()
        voice = status["voice"]
        selected = voice["selected"]
        if selected == "LOCAL":
            voice_text = "lokalny — aktywny domyślnie, bez zewnętrznych opłat"
        elif selected == "INVALID":
            voice_text = "nieznany wybór — działa bezpieczny głos lokalny"
        elif voice["configured"]:
            voice_text = (
                f"{selected.title()} — skonfigurowany; głos lokalny pozostaje awaryjny"
            )
        else:
            voice_text = (
                f"{selected.title()} — wybrany, ale wymaga klucza i identyfikatora głosu; "
                "działa głos lokalny"
            )

        azure = status["azure"]
        planner = "skonfigurowany" if azure["planner_configured"] else "wymaga konfiguracji"
        phone = (
            "skonfigurowana"
            if azure["phone_queue_configured"]
            else "wymaga konfiguracji"
        )
        lines = [
            "Integracje JARVIS OS:",
            f"• Głos: {voice_text}.",
            f"• Azure: planner {planner}; kolejka telefonu {phone}.",
        ]
        labels = {
            "revenuecat": ("RevenueCat", "tylko do odczytu"),
            "meta_ads": ("Meta Ads", "tylko do odczytu"),
            "claude": ("Claude", "wyłącznie do bezpiecznego rozumowania"),
        }
        for name, (label, ready_detail) in labels.items():
            provider = status["external"][name]
            if not provider["enabled"]:
                detail = "wyłączony"
            elif provider["ready"]:
                detail = f"skonfigurowany, {ready_detail}"
            elif provider["configuration_error"] == "missing_secret":
                detail = "włączony, ale wymaga lokalnego klucza"
            elif provider["configuration_error"] == "invalid_model":
                detail = "włączony, ale wymaga poprawnego modelu"
            elif provider["configuration_error"] in _ENDPOINT_ERRORS:
                detail = "włączony, ale wymaga zweryfikowanego adresu HTTPS"
            else:
                detail = "włączony, ale wymaga poprawnej konfiguracji"
            lines.append(f"• {label}: {detail}.")
        lines.append(
            "To lokalny odczyt ustawień: nie wykonano połączeń i nie wyświetlono kluczy."
        )
        return "\n".join(lines)


__all__ = ["IntegrationStatusService"]
