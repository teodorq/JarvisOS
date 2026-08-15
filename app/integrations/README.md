# Optional external integrations

This package prepares, but does not automatically send, requests for three
optional services. All integrations are disabled by default and credentials are
read only from the ignored `config/cloud.env` file or the process environment.

## RevenueCat MCP

- Fixed HTTPS endpoint: `https://mcp.revenuecat.ai/mcp`
- Enable with `JARVIS_OS_REVENUECAT_MCP_ENABLED=true`.
- Add a dedicated, read-only API v2 key as
  `JARVIS_OS_REVENUECAT_MCP_TOKEN`.
- JARVIS OS rejects every tool whose name is unknown or suggests a mutation.

## Meta Ads MCP

No Meta Ads MCP endpoint is treated as official by this repository. Before
enabling a reviewed connector, configure both
`JARVIS_OS_META_ADS_MCP_URL` and its exact DNS hostname in
`JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS`. Add a read-only credential as
`JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN`. Private addresses, HTTP, URL credentials,
query strings, fragments and mutation tools are rejected.

## Claude

Claude is optional and reasoning-only. Enable it with
`JARVIS_OS_CLAUDE_ENABLED=true`, select a verified pinned model with
`JARVIS_OS_CLAUDE_MODEL`, and store the key as `ANTHROPIC_API_KEY`. The
adapter does not expose JARVIS tools and requires an explicit
`remote_content_approved=True` decision for every prepared request.

The `status()` output reports missing secret variable names but never returns
secret values.
