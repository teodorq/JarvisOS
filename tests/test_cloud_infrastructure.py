from __future__ import annotations

import unittest
from pathlib import Path

from infra.azure.verify_deployment import verify_deployment


SHA = "a" * 40
IMAGE = f"ghcr.io/teodorq/jarvis-os-cloud:sha-{SHA}"
TENANT = "11111111-2222-3333-4444-555555555555"
OWNER = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CLIENT = "12345678-1234-1234-1234-123456789abc"


def _probe(
    probe_type: str,
    *,
    initial: int,
    period: int,
    timeout: int,
    failures: int,
) -> dict:
    return {
        "type": probe_type,
        "httpGet": {"path": "/health", "port": 8000, "scheme": "HTTP"},
        "initialDelaySeconds": initial,
        "periodSeconds": period,
        "timeoutSeconds": timeout,
        "failureThreshold": failures,
        "successThreshold": 1,
    }


def _app() -> dict:
    return {
        "name": "jarvis-os-planner",
        "location": "Poland Central",
        "tags": {
            "application": "JARVIS OS",
            "component": "cloud-planner",
            "costProfile": "4-60-eur-budget-alert",
        },
        "properties": {
            "provisioningState": "Succeeded",
            "runningStatus": "Running",
            "managedEnvironmentId": (
                "/subscriptions/test/resourceGroups/rg-jarvis-os-cloud/"
                "providers/Microsoft.App/managedEnvironments/jarvis-os-env"
            ),
            "configuration": {
                "activeRevisionsMode": "Single",
                "ingress": {
                    "external": True,
                    "allowInsecure": False,
                    "targetPort": 8000,
                    "transport": "Auto",
                    "traffic": [
                        {"latestRevision": True, "weight": 100}
                    ],
                },
                "secrets": [
                    {"name": "api-token"},
                    {"name": "phone-entra-client-secret"},
                    {"name": "remote-storage-connection"},
                ],
            },
            "template": {
                "scale": {"minReplicas": 0, "maxReplicas": 1},
                "containers": [
                    {
                        "name": "planner",
                        "image": IMAGE,
                        "resources": {"cpu": 0.25, "memory": "0.5Gi"},
                        "env": [
                            {
                                "name": "JARVIS_OS_CLOUD_ENVIRONMENT",
                                "value": "production",
                            },
                            {"name": "JARVIS_OS_BUILD_SHA", "value": SHA},
                            {
                                "name": "JARVIS_OS_CLOUD_API_TOKEN",
                                "secretRef": "api-token",
                            },
                            {
                                "name": "JARVIS_OS_PHONE_PRINCIPAL_ID",
                                "value": OWNER,
                            },
                            {
                                "name": "JARVIS_OS_REMOTE_STORAGE_CONNECTION",
                                "secretRef": "remote-storage-connection",
                            },
                            {
                                "name": "JARVIS_OS_REMOTE_TABLE",
                                "value": "commands",
                            },
                            {
                                "name": "JARVIS_OS_REMOTE_QUEUE",
                                "value": "commands",
                            },
                            {
                                "name": "JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE",
                                "value": "30",
                            },
                            {"name": "PORT", "value": "8000"},
                        ],
                        "probes": [
                            _probe(
                                "Startup",
                                initial=1,
                                period=2,
                                timeout=1,
                                failures=10,
                            ),
                            _probe(
                                "Readiness",
                                initial=1,
                                period=10,
                                timeout=2,
                                failures=3,
                            ),
                            _probe(
                                "Liveness",
                                initial=5,
                                period=30,
                                timeout=2,
                                failures=3,
                            ),
                        ],
                    }
                ],
            },
        },
    }


def _auth() -> dict:
    return {
        "platform": {"enabled": True},
        "globalValidation": {
            "unauthenticatedClientAction": "AllowAnonymous"
        },
        "httpSettings": {
            "requireHttps": True,
            "routes": {"apiPrefix": "/.auth"},
        },
        "identityProviders": {
            "azureActiveDirectory": {
                "registration": {
                    "clientId": CLIENT,
                    "clientSecretSettingName": "phone-entra-client-secret",
                    "openIdIssuer": (
                        f"https://login.microsoftonline.com/{TENANT}/v2.0"
                    ),
                },
                "validation": {
                    "allowedAudiences": [CLIENT],
                    "defaultAuthorizationPolicy": {
                        "allowedPrincipals": {"identities": [OWNER]}
                    },
                },
            }
        },
        "login": {
            "cookieExpiration": {
                "convention": "FixedTime",
                "timeToExpiration": "01:00:00",
            },
            "preserveUrlFragmentsForLogins": False,
            "tokenStore": {"enabled": False},
        },
    }


def _verify(app: dict, auth: dict) -> list[str]:
    return verify_deployment(
        app,
        auth,
        expected_image=IMAGE,
        expected_build_sha=SHA,
        expected_tenant_id=TENANT,
    )


class CloudInfrastructureTests(unittest.TestCase):
    def test_declared_runtime_and_authentication_are_accepted(self) -> None:
        self.assertEqual(_verify(_app(), _auth()), [])

    def test_cost_or_revision_drift_fails_the_deployment(self) -> None:
        cases = {
            "image": (
                lambda app, _auth: app["properties"]["template"][
                    "containers"
                ][0].update({"image": "ghcr.io/wrong/image:latest"}),
                "container image drift",
            ),
            "replicas": (
                lambda app, _auth: app["properties"]["template"][
                    "scale"
                ].update({"maxReplicas": 5}),
                "maximum replica drift",
            ),
            "build": (
                lambda app, _auth: app["properties"]["template"][
                    "containers"
                ][0]["env"][1].update({"value": "b" * 40}),
                "JARVIS_OS_BUILD_SHA drift",
            ),
        }
        for name, (mutate, expected) in cases.items():
            with self.subTest(name=name):
                app, auth = _app(), _auth()
                mutate(app, auth)
                self.assertIn(expected, _verify(app, auth))

    def test_quoted_owner_or_auth_route_drift_is_rejected(self) -> None:
        quoted = _auth()
        quoted["identityProviders"]["azureActiveDirectory"]["validation"][
            "defaultAuthorizationPolicy"
        ]["allowedPrincipals"]["identities"] = [f"'{OWNER}'"]
        self.assertIn(
            "EasyAuth owner principal differs from the planner owner",
            _verify(_app(), quoted),
        )

        missing_route = _auth()
        missing_route["httpSettings"]["routes"] = {}
        self.assertIn(
            "EasyAuth API prefix drift",
            _verify(_app(), missing_route),
        )

    def test_workflow_compiles_bicep_and_checks_live_configuration(self) -> None:
        workflow = Path(".github/workflows/cloud-image.yml").read_text(
            encoding="utf-8"
        )
        for expected in (
            "infra/azure/**",
            "az bicep build",
            "--cpu 0.25",
            "--memory 0.5Gi",
            "--min-replicas 0",
            "--max-replicas 1",
            "verify_deployment.py",
            "az containerapp auth show",
        ):
            self.assertIn(expected, workflow)

        main_bicep = Path("infra/azure/main.bicep").read_text(
            encoding="utf-8"
        )
        subscription_bicep = Path(
            "infra/azure/subscription.bicep"
        ).read_text(encoding="utf-8")
        self.assertIn("param buildSha string", main_bicep)
        self.assertIn("name: 'JARVIS_OS_BUILD_SHA'", main_bicep)
        self.assertIn("buildSha: buildSha", subscription_bicep)

    def test_drift_checks_do_not_embed_live_owner_identifiers(self) -> None:
        live_owner = "-".join(
            ("77f4b7fe", "8e18", "498b", "8898", "84befa780edb")
        )
        sources = (
            Path("infra/azure/verify_deployment.py").read_text(
                encoding="utf-8"
            )
            + Path("tests/test_cloud_infrastructure.py").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn(live_owner, sources)


if __name__ == "__main__":
    unittest.main()
