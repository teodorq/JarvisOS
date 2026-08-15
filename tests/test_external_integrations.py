from __future__ import annotations

import unittest

from app.integrations.external_services import (
    ClaudeMessagesAdapter,
    ExternalIntegrationError,
    ExternalIntegrationRegistry,
    SafeMcpAdapter,
)


class ExternalIntegrationTests(unittest.TestCase):
    def test_all_integrations_are_disabled_by_default(self) -> None:
        registry = ExternalIntegrationRegistry({})
        status = registry.status()
        self.assertFalse(status["revenuecat"]["enabled"])
        self.assertFalse(status["meta_ads"]["enabled"])
        self.assertFalse(status["claude"]["enabled"])
        self.assertEqual(
            status["revenuecat"]["endpoint_host"],
            "mcp.revenuecat.ai",
        )
        self.assertEqual(status["meta_ads"]["endpoint_host"], "")

    def test_revenuecat_requires_secret_and_fixed_official_endpoint(self) -> None:
        missing = ExternalIntegrationRegistry(
            {"JARVIS_OS_REVENUECAT_MCP_ENABLED": "true"}
        ).settings("revenuecat")
        self.assertEqual(missing.configuration_error, "missing_secret")
        with self.assertRaisesRegex(ExternalIntegrationError, "missing_secret"):
            SafeMcpAdapter(missing).prepare_tools_list()

        unsafe = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_REVENUECAT_MCP_ENABLED": "true",
                "JARVIS_OS_REVENUECAT_MCP_URL": "https://evil.example/mcp",
                "JARVIS_OS_REVENUECAT_MCP_TOKEN": "secret-rc",
            }
        ).settings("revenuecat")
        self.assertEqual(unsafe.configuration_error, "host_not_allowlisted")

    def test_revenuecat_prepares_read_only_mcp_without_leaking_token(self) -> None:
        settings = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_REVENUECAT_MCP_ENABLED": "yes",
                "JARVIS_OS_REVENUECAT_MCP_TOKEN": "secret-rc",
            }
        ).settings("revenuecat")
        adapter = SafeMcpAdapter(settings)
        request = adapter.prepare_tool_call(
            "revenuecat_get_chart", {"project_id": "p1"}
        )
        self.assertTrue(settings.ready)
        self.assertEqual(request.payload["method"], "tools/call")
        self.assertEqual(request.payload["params"]["name"], "revenuecat_get_chart")
        self.assertEqual(request.headers["Authorization"], "Bearer secret-rc")
        self.assertNotIn("secret-rc", repr(request))
        self.assertNotIn("secret-rc", repr(settings))
        changed = request.payload
        changed["method"] = "dangerous/mutation"
        self.assertEqual(request.payload["method"], "tools/call")

    def test_mcp_tools_are_strictly_read_only(self) -> None:
        settings = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_REVENUECAT_MCP_ENABLED": "true",
                "JARVIS_OS_REVENUECAT_MCP_TOKEN": "secret-rc",
            }
        ).settings("revenuecat")
        adapter = SafeMcpAdapter(settings)
        for tool in (
            "revenuecat_create_project",
            "get_or_delete_customer",
            "pause_campaign",
            "custom_operation",
        ):
            with self.subTest(tool=tool), self.assertRaises(ExternalIntegrationError):
                adapter.prepare_tool_call(tool)

    def test_sensitive_values_cannot_be_smuggled_in_tool_arguments(self) -> None:
        settings = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_REVENUECAT_MCP_ENABLED": "true",
                "JARVIS_OS_REVENUECAT_MCP_TOKEN": "secret-rc",
            }
        ).settings("revenuecat")
        with self.assertRaisesRegex(ExternalIntegrationError, "sensitive"):
            SafeMcpAdapter(settings).prepare_tool_call(
                "get_project", {"filter": {"userAccessToken": "do-not-send"}}
            )

    def test_meta_requires_reviewed_https_host_allowlist(self) -> None:
        registry = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_META_ADS_MCP_ENABLED": "true",
                "JARVIS_OS_META_ADS_MCP_URL": "https://reviewed.example/mcp",
                "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS": "reviewed.example",
                "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN": "secret-meta",
            }
        )
        settings = registry.settings("meta_ads")
        self.assertTrue(settings.ready)
        request = SafeMcpAdapter(settings).prepare_tool_call(
            "meta_ads_get_insights", {"campaign_id": "123"}
        )
        self.assertEqual(request.url, "https://reviewed.example/mcp")

        not_allowlisted = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_META_ADS_MCP_ENABLED": "true",
                "JARVIS_OS_META_ADS_MCP_URL": "https://other.example/mcp",
                "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS": "reviewed.example",
                "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN": "secret-meta",
            }
        ).settings("meta_ads")
        self.assertEqual(not_allowlisted.configuration_error, "host_not_allowlisted")

    def test_private_or_plain_http_meta_endpoint_is_rejected(self) -> None:
        cases = (
            ("http://reviewed.example/mcp", "reviewed.example", "https_required"),
            ("https://127.0.0.1/mcp", "127.0.0.1", "public_dns_host_required"),
        )
        for endpoint, hosts, expected in cases:
            with self.subTest(endpoint=endpoint):
                settings = ExternalIntegrationRegistry(
                    {
                        "JARVIS_OS_META_ADS_MCP_ENABLED": "true",
                        "JARVIS_OS_META_ADS_MCP_URL": endpoint,
                        "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS": hosts,
                        "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN": "secret-meta",
                    }
                ).settings("meta_ads")
                self.assertEqual(settings.configuration_error, expected)

    def test_claude_is_reasoning_only_and_requires_per_request_approval(self) -> None:
        settings = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_CLAUDE_ENABLED": "true",
                "JARVIS_OS_CLAUDE_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_API_KEY": "secret-claude",
            }
        ).settings("claude")
        adapter = ClaudeMessagesAdapter(settings)
        with self.assertRaisesRegex(ExternalIntegrationError, "not_approved"):
            adapter.prepare_message("Przeanalizuj plan")
        with self.assertRaisesRegex(ExternalIntegrationError, "not_approved"):
            adapter.prepare_message("Przeanalizuj plan", remote_content_approved=1)
        request = adapter.prepare_message(
            "Przeanalizuj plan", remote_content_approved=True, max_tokens=300
        )
        self.assertEqual(request.url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.payload["model"], "claude-sonnet-4-6")
        self.assertNotIn("tools", request.payload)
        self.assertEqual(request.headers["x-api-key"], "secret-claude")
        self.assertNotIn("secret-claude", repr(request))
        self.assertNotIn("secret-claude", repr(settings))

    def test_claude_requires_explicit_model_and_exact_api_endpoint(self) -> None:
        missing_model = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_CLAUDE_ENABLED": "true",
                "ANTHROPIC_API_KEY": "secret-claude",
            }
        ).settings("claude")
        self.assertEqual(missing_model.configuration_error, "invalid_model")

        unsafe = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_CLAUDE_ENABLED": "true",
                "JARVIS_OS_CLAUDE_API_URL": "https://api.anthropic.com/v1/models",
                "JARVIS_OS_CLAUDE_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_API_KEY": "secret-claude",
            }
        ).settings("claude")
        self.assertEqual(unsafe.configuration_error, "path_not_allowlisted")

    def test_status_reports_secret_name_but_never_secret_value(self) -> None:
        registry = ExternalIntegrationRegistry(
            {"JARVIS_OS_CLAUDE_ENABLED": "true"}
        )
        status = registry.status()["claude"]
        self.assertEqual(status["required_secret"], "ANTHROPIC_API_KEY")
        self.assertNotIn("token", status)

    def test_status_does_not_echo_credentials_embedded_in_bad_endpoint(self) -> None:
        status = ExternalIntegrationRegistry(
            {
                "JARVIS_OS_META_ADS_MCP_ENABLED": "true",
                "JARVIS_OS_META_ADS_MCP_URL":
                    "https://user:password@reviewed.example/mcp?token=secret",
                "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS": "reviewed.example",
                "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN": "secret-meta",
            }
        ).status()["meta_ads"]
        rendered = repr(status)
        self.assertNotIn("password", rendered)
        self.assertNotIn("token=secret", rendered)


if __name__ == "__main__":
    unittest.main()
