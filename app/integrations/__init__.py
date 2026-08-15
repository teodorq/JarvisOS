"""Opt-in external service adapters for JARVIS OS."""

from app.integrations.external_services import (
    ClaudeMessagesAdapter,
    ExternalIntegrationError,
    ExternalIntegrationRegistry,
    IntegrationSettings,
    PreparedExternalRequest,
    SafeMcpAdapter,
)

__all__ = [
    "ClaudeMessagesAdapter",
    "ExternalIntegrationError",
    "ExternalIntegrationRegistry",
    "IntegrationSettings",
    "PreparedExternalRequest",
    "SafeMcpAdapter",
]
