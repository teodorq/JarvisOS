"""Opt-in external service adapters for JARVIS OS."""

from app.integrations.external_services import (
    ClaudeMessagesAdapter,
    ExternalIntegrationError,
    ExternalIntegrationRegistry,
    IntegrationSettings,
    PreparedExternalRequest,
    SafeMcpAdapter,
)
from app.integrations.status import IntegrationStatusService

__all__ = [
    "ClaudeMessagesAdapter",
    "ExternalIntegrationError",
    "ExternalIntegrationRegistry",
    "IntegrationSettings",
    "IntegrationStatusService",
    "PreparedExternalRequest",
    "SafeMcpAdapter",
]
