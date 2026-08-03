# JARVIS OS Cloud - stage 1

This stage moves only safe, read-oriented planning to Azure. The GUI,
microphone, Windows action execution, user confirmations, memory, and Google
tokens remain on the desktop computer.

## Cost guardrails

- Azure Container Apps Consumption plan.
- minReplicas: 0, so there is no replica while idle.
- maxReplicas: 1, preventing horizontal scaling.
- 0.25 vCPU and 0.5 GiB RAM.
- At most 30 authenticated planning requests per minute and source.
- A failed cloud call opens a 60-second local fallback circuit on the desktop.
- No database, Azure Container Registry, private network, or paid Log
  Analytics workspace in this stage.
- The 20 PLN budget is an alert, not a custom hard spending cap.

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
4. Deploy subscription.bicep with the full image name and a random API token
   passed as secure parameters. Never store that token in a file or Git.
5. Check the returned /health URL before configuring JARVIS_OS_CLOUD_URL and
   JARVIS_OS_CLOUD_API_TOKEN on the desktop.

The previous JARVIS_CLOUD_* names remain accepted temporarily as migration
aliases, but all new configuration should use JARVIS_OS_CLOUD_*.

Do not deploy an image tagged only as latest. Use an immutable version tag or
Git commit hash so a controlled rollback remains possible.
