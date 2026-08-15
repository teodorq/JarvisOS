# JARVIS OS Cloud

This architecture moves safe planning and a durable phone command relay to Azure. The
GUI, microphone, Windows action execution, user confirmations, memory, and
Google tokens remain on the desktop computer.

The cloud boundary adds a privacy gate on both sides of the connection. Commands that
look like they contain passwords, API keys, bearer tokens, private keys, or
provider credentials stay on the desktop and use the local planner. Azure
also receives startup, readiness, and liveness probes without adding another
paid service.

## Cost guardrails

- Azure Container Apps Consumption plan.
- minReplicas: 0, so there is no replica while idle.
- maxReplicas: 1, preventing horizontal scaling.
- 0.25 vCPU and 0.5 GiB RAM.
- At most 30 authenticated planning requests per minute and source.
- A failed cloud call opens a 60-second local fallback circuit on the desktop.
- One Standard_LRS Storage account keeps short-lived relay records and queue
  messages. Shared Key authorization is disabled. The Container App uses its
  managed identity, while the owner receives message-processing access only to
  the `commands` queue.
- Commands containing likely credentials never leave the desktop; the cloud
  service rejects them as a second line of defense.
- The subscription has a 4.60 EUR monthly budget with alerts at 50%, 80%,
  and 100%. `budget.bicep` declares this guardrail without publishing the
  private alert address. It is an alert, not a custom hard spending cap.

## Local smoke test

Set the same temporary random token in two terminals. In the first terminal:

~~~powershell
$env:JARVIS_OS_CLOUD_ENVIRONMENT = "development"
$env:JARVIS_OS_CLOUD_API_TOKEN = "local-test-token"
.\.venv\Scripts\python.exe -m cloud_service.main
~~~

In the second terminal, configure the JARVIS client:

~~~powershell
$env:JARVIS_OS_CLOUD_URL = "http://127.0.0.1:8000"
$env:JARVIS_OS_CLOUD_API_TOKEN = "local-test-token"
.\.venv\Scripts\python.exe main.py
~~~

Without those variables, JARVIS behaves as it did before this stage. On a
network failure, cold-start timeout, or rejected cloud plan, the client
automatically uses the local planner.

## Deployment preparation

1. Build the image from the repository root:

   docker build -f cloud_service/Dockerfile -t <registry>/jarvis-os-cloud-planner:<tag> .

2. Publish the image to a trusted registry. The template intentionally does
   not create a paid Azure Container Registry; the selected image must be
   accessible to Container Apps.
3. Install Azure CLI, sign in, and explicitly select the correct subscription.
4. Register the phone page in Microsoft Entra with the Container Apps callback
   URL, create a client secret, and note the owner's Entra object ID.
5. Deploy subscription.bicep with the image, desktop API token, Entra client
   ID and secret, owner object ID, and `budgetAlertEmail` passed as secure
   parameters. Never store those private values in a file or Git.
6. Check the returned /health URL before configuring JARVIS_OS_CLOUD_URL and
   JARVIS_OS_CLOUD_API_TOKEN on the desktop.

Only the JARVIS_OS_CLOUD_* names are accepted. The temporary JARVIS_CLOUD_*
migration aliases were removed after the live deployment moved to JARVIS OS.

## Private phone command page

The deployment returns a `/phone` URL. Container Apps authenticates the owner
through Microsoft Entra and issues a fixed 60-minute cookie. The application
checks the injected provider and exact owner object ID again before accepting
commands. The page supports PWA installation, logout, lost-device session
review, and restoration of the last command status after refresh. It stores
only command and device identifiers in `sessionStorage`, never command text or
results. The desktop must remain running to receive commands. The phone cannot
approve actions: anything protected by the normal confirmation policy still
waits for local confirmation on the computer.

Each phone submission carries a random idempotency key. A retry with the same
device, command, and key returns the existing 24-hour record and does not send
a second Azure Queue message. Reusing the key for different content is rejected
with HTTP 409. The browser stores only the key and a SHA-256 signature for an
unfinished submission, never the command text.

Do not deploy an image tagged only as latest. Use an immutable version tag or
Git commit hash so a controlled rollback remains possible.

## Continuous deployment

Changes to the cloud boundary on `develop` are tested and published as an
immutable `sha-<commit>` image by GitHub Actions. The workflow then signs in
to Azure through OpenID Connect, reapplies the declared CPU, memory, replica,
environment and image settings to `jarvis-os-planner`, and waits for the
public health check. It compiles `subscription.bicep` before publishing and
compares the live Container App and EasyAuth configuration with the checked-in
runtime contract after deployment. A mismatched image, build SHA, cost limit,
probe, secret reference, Entra owner, audience, issuer, or login policy fails
the workflow instead of silently accepting configuration drift.

No Azure password, Storage key, desktop token, or Entra client secret is
stored in GitHub or passed to the Container App.
The federated identity accepts tokens only from this repository's `develop`
and `main` branches and has Container Apps Contributor access only to the
planner resource. Develop publishes production images; main runs the scheduled
health monitor and the manual rollback workflow.
Storage-account and identity changes remain deliberate Bicep deployments. The
runtime declaration verifies that the managed identity is present and that no
Storage connection-string secret returns. Container startup also performs a
non-destructive Table entity read and Queue message peek, so a missing data
role or unavailable relay prevents a falsely healthy deployment.

`cloud-health-monitor.yml` performs one scheduled health check each day and
fails if the immutable build, Azure Queue relay, or managed-identity Storage
access is unavailable. `cloud-rollback.yml` is a manual, serialized recovery
workflow: provide a full 40-character commit SHA whose immutable image was
already published. It restores that exact image and accepts success only after
the same health and public-route checks pass. Deployment and rollback share one
production lock, so they cannot modify the Container App concurrently.

## Local Azure guardrail audit

The live authentication and budget documents stay on the owner's computer.
`tools/audit_azure_guardrails.ps1` performs a read-only check of the active
subscription, managed identity roles, Storage security, budget thresholds,
GitHub federation, deployment permissions, and public cloud health. Its log
contains only a safe OK/FAILED summary and never includes the private alert
address, tokens, secrets, or Azure object identifiers.

`tools/install_azure_guardrail_audit.ps1` installs the audit as a hidden
Windows task for every Monday at 09:00 and runs it once immediately. Results
are written under `runtime/`, which is excluded from Git.
