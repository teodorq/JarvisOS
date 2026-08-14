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
- One Standard_LRS Table Storage account keeps short-lived relay records for
  24 hours. There is no Azure Container Registry, private network, or paid Log
  Analytics workspace in this stage.
- Commands containing likely credentials never leave the desktop; the cloud
  service rejects them as a second line of defense.
- The subscription has a 4.60 EUR monthly budget with alerts at 50%, 80%,
  and 100%. It is an alerting guardrail, not a custom hard spending cap.

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
   ID and secret, and owner object ID passed as secure parameters. Never store
   the desktop token or Entra secret in a file or Git.
6. Check the returned /health URL before configuring JARVIS_OS_CLOUD_URL and
   JARVIS_OS_CLOUD_API_TOKEN on the desktop.

The previous JARVIS_CLOUD_* names remain accepted temporarily as migration
aliases, but all new configuration should use JARVIS_OS_CLOUD_*.

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

No Azure password, desktop token, or Entra client secret is stored in GitHub.
The federated identity accepts tokens only from this repository's `develop`
branch and has Container Apps Contributor access only to the planner resource.
Storage-account and identity changes remain deliberate Bicep deployments until
the relay moves from a shared storage key to managed identity and RBAC.
