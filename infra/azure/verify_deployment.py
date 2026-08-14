"""Fail a deployment when the live Container App drifts from JARVIS OS IaC."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _read_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _environment(
    errors: list[str], container: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    entries = container.get("env") or []
    result = {
        str(entry.get("name", "")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("name")
    }
    _require(
        errors,
        len(result) == len(entries),
        "container environment contains duplicate or unnamed entries",
    )
    return result


def _verify_probe(
    errors: list[str],
    probes: dict[str, dict[str, Any]],
    probe_type: str,
    expected: dict[str, Any],
) -> None:
    probe = probes.get(probe_type, {})
    _require(errors, bool(probe), f"{probe_type} probe is missing")
    for key, value in expected.items():
        _require(
            errors,
            probe.get(key) == value,
            f"{probe_type} probe has unexpected {key}",
        )
    http_get = probe.get("httpGet") or {}
    _require(
        errors,
        http_get.get("path") == "/health"
        and http_get.get("port") == 8000
        and str(http_get.get("scheme", "")).upper() == "HTTP",
        f"{probe_type} probe does not target HTTP /health on port 8000",
    )


def verify_deployment(
    app: dict[str, Any],
    auth: dict[str, Any],
    *,
    expected_image: str,
    expected_build_sha: str,
    expected_tenant_id: str,
) -> list[str]:
    """Return human-readable drift failures without exposing secret values."""
    errors: list[str] = []
    properties = app.get("properties") or {}
    configuration = properties.get("configuration") or {}
    template = properties.get("template") or {}
    ingress = configuration.get("ingress") or {}

    _require(errors, app.get("name") == "jarvis-os-planner", "app name drift")
    _require(
        errors,
        str(app.get("location", "")).replace(" ", "").lower()
        == "polandcentral",
        "app location drift",
    )
    _require(
        errors,
        properties.get("provisioningState") == "Succeeded",
        "app provisioning is not successful",
    )
    _require(
        errors,
        properties.get("runningStatus") == "Running",
        "app is not running",
    )
    _require(
        errors,
        str(properties.get("managedEnvironmentId", "")).lower().endswith(
            "/managedenvironments/jarvis-os-env"
        ),
        "managed environment drift",
    )

    tags = app.get("tags") or {}
    _require(errors, tags.get("application") == "JARVIS OS", "application tag drift")
    _require(errors, tags.get("component") == "cloud-planner", "component tag drift")
    _require(
        errors,
        tags.get("costProfile") == "4-60-eur-budget-alert",
        "cost profile tag drift",
    )

    _require(
        errors,
        configuration.get("activeRevisionsMode") == "Single",
        "revision mode is not Single",
    )
    _require(errors, ingress.get("external") is True, "ingress is not external")
    _require(
        errors, ingress.get("allowInsecure") is False, "insecure ingress is enabled"
    )
    _require(errors, ingress.get("targetPort") == 8000, "ingress port drift")
    _require(
        errors,
        str(ingress.get("transport", "")).lower() == "auto",
        "ingress transport drift",
    )
    traffic = ingress.get("traffic") or []
    _require(
        errors,
        len(traffic) == 1
        and traffic[0].get("latestRevision") is True
        and traffic[0].get("weight") == 100,
        "traffic is not pinned 100% to the latest revision",
    )

    secret_names = {
        item.get("name")
        for item in (configuration.get("secrets") or [])
        if isinstance(item, dict)
    }
    _require(
        errors,
        secret_names
        == {
            "api-token",
            "phone-entra-client-secret",
            "remote-storage-connection",
        },
        "Container App secret references drifted",
    )

    containers = template.get("containers") or []
    _require(
        errors,
        len(containers) == 1 and containers[0].get("name") == "planner",
        "planner container layout drift",
    )
    if not containers:
        return errors
    container = containers[0]
    _require(errors, container.get("image") == expected_image, "container image drift")
    resources = container.get("resources") or {}
    _require(errors, float(resources.get("cpu", 0)) == 0.25, "CPU limit drift")
    _require(errors, resources.get("memory") == "0.5Gi", "memory limit drift")

    scale = template.get("scale") or {}
    _require(errors, scale.get("minReplicas") == 0, "minimum replica drift")
    _require(errors, scale.get("maxReplicas") == 1, "maximum replica drift")

    env = _environment(errors, container)
    expected_values = {
        "JARVIS_OS_CLOUD_ENVIRONMENT": "production",
        "JARVIS_OS_BUILD_SHA": expected_build_sha,
        "JARVIS_OS_REMOTE_TABLE": "commands",
        "JARVIS_OS_REMOTE_QUEUE": "commands",
        "JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE": "30",
        "PORT": "8000",
    }
    for name, value in expected_values.items():
        _require(
            errors,
            env.get(name, {}).get("value") == value,
            f"{name} drift",
        )
    expected_secrets = {
        "JARVIS_OS_CLOUD_API_TOKEN": "api-token",
        "JARVIS_OS_REMOTE_STORAGE_CONNECTION": "remote-storage-connection",
    }
    for name, secret_ref in expected_secrets.items():
        _require(
            errors,
            env.get(name, {}).get("secretRef") == secret_ref,
            f"{name} secret reference drift",
        )
    _require(
        errors,
        not any(name.startswith("JARVIS_CLOUD_") for name in env),
        "legacy JARVIS_CLOUD environment names are deployed",
    )

    phone_owner = str(
        env.get("JARVIS_OS_PHONE_PRINCIPAL_ID", {}).get("value", "")
    ).lower()
    _require(
        errors,
        bool(UUID_PATTERN.fullmatch(phone_owner)),
        "phone owner principal is not a clean UUID",
    )
    _require(
        errors,
        bool(SHA_PATTERN.fullmatch(expected_build_sha)),
        "expected build SHA is invalid",
    )

    probes = {
        str(item.get("type", "")): item
        for item in (container.get("probes") or [])
        if isinstance(item, dict)
    }
    _require(
        errors,
        set(probes) == {"Startup", "Readiness", "Liveness"},
        "probe set drift",
    )
    _verify_probe(
        errors,
        probes,
        "Startup",
        {
            "initialDelaySeconds": 1,
            "periodSeconds": 2,
            "timeoutSeconds": 1,
            "failureThreshold": 10,
            "successThreshold": 1,
        },
    )
    _verify_probe(
        errors,
        probes,
        "Readiness",
        {
            "initialDelaySeconds": 1,
            "periodSeconds": 10,
            "timeoutSeconds": 2,
            "failureThreshold": 3,
            "successThreshold": 1,
        },
    )
    _verify_probe(
        errors,
        probes,
        "Liveness",
        {
            "initialDelaySeconds": 5,
            "periodSeconds": 30,
            "timeoutSeconds": 2,
            "failureThreshold": 3,
            "successThreshold": 1,
        },
    )

    auth_properties = auth.get("properties", auth)
    _require(
        errors,
        auth_properties.get("platform", {}).get("enabled") is True,
        "EasyAuth platform is disabled",
    )
    _require(
        errors,
        auth_properties.get("globalValidation", {}).get(
            "unauthenticatedClientAction"
        )
        == "AllowAnonymous",
        "EasyAuth anonymous action drift",
    )
    http_settings = auth_properties.get("httpSettings") or {}
    _require(errors, http_settings.get("requireHttps") is True, "EasyAuth HTTPS drift")
    _require(
        errors,
        http_settings.get("routes", {}).get("apiPrefix") == "/.auth",
        "EasyAuth API prefix drift",
    )

    aad = auth_properties.get("identityProviders", {}).get(
        "azureActiveDirectory", {}
    )
    registration = aad.get("registration") or {}
    client_id = str(registration.get("clientId", "")).lower()
    _require(
        errors,
        bool(UUID_PATTERN.fullmatch(client_id)),
        "Entra client ID is invalid",
    )
    _require(
        errors,
        registration.get("clientSecretSettingName")
        == "phone-entra-client-secret",
        "Entra secret reference drift",
    )
    _require(
        errors,
        registration.get("openIdIssuer")
        == f"https://login.microsoftonline.com/{expected_tenant_id}/v2.0",
        "Entra issuer drift",
    )
    validation = aad.get("validation") or {}
    _require(
        errors,
        validation.get("allowedAudiences") == [client_id],
        "Entra allowed audience drift",
    )
    allowed_owners = (
        validation.get("defaultAuthorizationPolicy", {})
        .get("allowedPrincipals", {})
        .get("identities")
    )
    _require(
        errors,
        allowed_owners == [phone_owner],
        "EasyAuth owner principal differs from the planner owner",
    )

    login = auth_properties.get("login") or {}
    _require(
        errors,
        login.get("cookieExpiration")
        == {
            "convention": "FixedTime",
            "timeToExpiration": "01:00:00",
        },
        "EasyAuth cookie policy drift",
    )
    _require(
        errors,
        login.get("preserveUrlFragmentsForLogins") is False,
        "EasyAuth fragment policy drift",
    )
    _require(
        errors,
        login.get("tokenStore", {}).get("enabled") is False,
        "EasyAuth token store drift",
    )
    _require(
        errors,
        "logoutEndpoint" not in login.get("routes", {}),
        "custom logout endpoint returned",
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-json", required=True)
    parser.add_argument("--auth-json", required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--expected-build-sha", required=True)
    parser.add_argument("--expected-tenant-id", required=True)
    arguments = parser.parse_args()
    try:
        errors = verify_deployment(
            _read_json(arguments.app_json),
            _read_json(arguments.auth_json),
            expected_image=arguments.expected_image,
            expected_build_sha=arguments.expected_build_sha.lower(),
            expected_tenant_id=arguments.expected_tenant_id.lower(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Azure drift verification could not read its inputs: {error}", file=sys.stderr)
        return 2
    if errors:
        print("Azure configuration drift detected:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Azure runtime and authentication match the JARVIS OS declaration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
