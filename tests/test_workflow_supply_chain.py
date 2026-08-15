from __future__ import annotations

import re
import unittest
from pathlib import Path


EXTERNAL_ACTION = re.compile(
    r"^\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)",
    re.MULTILINE,
)
IMMUTABLE_COMMIT = re.compile(r"^[a-f0-9]{40}$")


class WorkflowSupplyChainTests(unittest.TestCase):
    def test_every_external_action_is_pinned_to_a_commit(self) -> None:
        workflows = sorted(Path(".github/workflows").glob("*.y*ml"))
        self.assertTrue(workflows)
        found: list[tuple[Path, str, str]] = []
        for workflow in workflows:
            source = workflow.read_text(encoding="utf-8")
            for action, reference in EXTERNAL_ACTION.findall(source):
                found.append((workflow, action, reference))
                self.assertRegex(
                    reference,
                    IMMUTABLE_COMMIT,
                    f"{workflow}: {action} must use an immutable commit",
                )
        self.assertTrue(found)

    def test_dependabot_tracks_github_action_commits(self) -> None:
        config = Path(".github/dependabot.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("package-ecosystem: github-actions", config)
        self.assertIn("interval: weekly", config)
        self.assertIn("verified-github-actions", config)

    def test_published_cloud_image_has_signed_provenance(self) -> None:
        workflow = Path(".github/workflows/cloud-image.yml").read_text(
            encoding="utf-8"
        )
        required = (
            "artifact-metadata: write",
            "attestations: write",
            "id: publish",
            "Attest published image provenance",
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
            "subject-name: ghcr.io/${{ github.repository_owner }}"
            "/jarvis-os-cloud",
            "subject-digest: ${{ steps.publish.outputs.digest }}",
            "push-to-registry: true",
        )
        for marker in required:
            self.assertIn(marker, workflow)
        self.assertLess(
            workflow.index("Build and publish immutable image"),
            workflow.index("Attest published image provenance"),
        )
        self.assertLess(
            workflow.index("Attest published image provenance"),
            workflow.index("Deploy immutable image to Azure"),
        )


if __name__ == "__main__":
    unittest.main()
