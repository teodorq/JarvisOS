# JARVIS OS

JARVIS OS is a Windows desktop assistant with a local-first runtime and an optional Azure cloud planner.

## What stays local

User memory, command history, Google tokens, voice models, logs, generated backups and commercial release artifacts are runtime data. They are intentionally excluded from Git and are created locally when needed.

## Requirements

- Windows 10 or Windows 11
- Python 3.13 (the checkpoint was verified with Python 3.13.7)
- A microphone is optional
- Azure and Google integrations are optional

## Fresh installation

1. Clone the repository and switch to the `develop` branch.
2. Run `install.bat`.
3. Run `start_jarvis.bat`.

The installer creates a local `.venv` environment. It uses `requirements-lock.txt` when available, so the verified package versions are reproducible.

## Tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For a quick source check:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app cloud_service software_engineer tools
```

## Optional Google Workspace integration

Copy `config/google_workspace_client_secret.example.json` to a local credentials file and fill it with credentials from Google Cloud. Real client secrets and OAuth tokens must never be committed.

## Optional Azure planner

Copy `config/cloud.env.example` to `config/cloud.env` and provide:

- `JARVIS_OS_CLOUD_URL`
- `JARVIS_OS_CLOUD_API_TOKEN`

The desktop validates every cloud plan. Windows actions, confirmations and private memory remain local, and the local planner is used automatically if Azure is unavailable.

## Repository layout

- `app/` - desktop application and local capabilities
- `cloud_service/` - Azure planner service
- `infra/` - Azure infrastructure definitions
- `tests/` - regression and safety tests
- `tools/` - maintenance and verification utilities
- `data/`, `archive/`, `AI_PLIKI/`, `runtime/` - local runtime state, excluded from Git

## Security

The repository is public. Do not commit passwords, API tokens, OAuth files, private keys, user memory, logs or generated customer packages.
