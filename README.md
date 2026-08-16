# JARVIS OS

JARVIS OS is a Windows desktop assistant with a local-first runtime and an optional Azure cloud planner.

## What stays local

User memory, command history, Google tokens, voice models, logs, generated backups and commercial release artifacts are runtime data. They are intentionally excluded from Git and are created locally when needed.

## Requirements

- Windows 10 or Windows 11
- Python 3.13 (the checkpoint was verified with Python 3.13.7)
- A microphone is optional
- Azure and Google integrations are optional
- Cartesia and ElevenLabs text-to-speech are optional

## Fresh installation

1. Clone the repository and switch to the `develop` branch.
2. Run `install.bat`.
3. Run `start_jarvis.vbs` to start JARVIS OS without a console window.

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
- `JARVIS_OS_REMOTE_DEVICE_ID=desktop-main` to receive commands from the
  private phone page
- `JARVIS_OS_REMOTE_QUEUE_URL` with the SAS-free queue URL; the signed-in
  Microsoft Entra user receives only queue-message processor permission

The desktop validates every cloud plan. Windows actions, confirmations and private memory remain local, and the local planner is used automatically if Azure is unavailable.

## Optional Cartesia or ElevenLabs voice

The existing local voice remains the default and needs no external account.
To opt in to a cloud voice, copy `config/voice.env.example` to the ignored
`config/voice.env` file and configure exactly one provider, its API key and a
voice ID. Use `JARVIS_OS_VOICE_PROVIDER=CARTESIA` or
`JARVIS_OS_VOICE_PROVIDER=ELEVENLABS`. API keys are never committed or shown in
voice status. Spoken text is sent to the selected provider only while it is
explicitly enabled. If credentials are absent, the request fails, the provider
times out or returns invalid audio, JARVIS OS repeats the same response using a
local Windows voice. Cloud audio is cached only under the ignored local
`runtime/voice_output/cloud_cache` directory.

Say or type `Pokaż status integracji` (or use `INTEGRACJE` in the daily tools)
to see the local configuration state of Azure, voice, RevenueCat, Meta Ads and
Claude. This status check makes no external request and never displays API keys
or private endpoint addresses.

The Azure deployment also exposes a private, installable `/phone` app. Access
uses the owner's Microsoft account and a fixed 60-minute Azure session instead
of a pairing code. Signing out invalidates the current session; the Microsoft
"My sign-ins" page can revoke a lost phone. The relay stores commands for at
most 24 hours and never bypasses the desktop confirmation policy. The page
restores the last command status after a refresh without storing its text.
Desktop command polling goes directly to Azure Storage Queue, so the Container
App can scale to zero while the phone page is not being used.
If a mobile connection drops during submission, the page safely reuses a
short-lived request identifier. Azure returns the original command instead of
placing a duplicate in the desktop queue; command text is not persisted in
browser storage.

For a reliable iPhone start, open `/mobile-start` in full Safari (not the
embedded browser of another app). It is a static page outside the phone Service
Worker and never redirects or signs out automatically. `/mobile-logout` exposes
an explicit Azure sign-out button, while `/mobile-diagnostics` shows only safe
connection checks and a request identifier that can be matched with server
logs. It never displays the owner's account identifier.
Microsoft returns an authorization code through the callback query instead of
a fragment that depends on callback JavaScript. Successful login stops at the
script-free `/mobile-complete` page so the owner can verify the session before
opening the panel with a normal tap.

## Optional Windows autostart

The phone bridge can receive commands only while the desktop application is
running. Install the per-user watchdog to start JARVIS OS after sign-in and
restart it after an unexpected exit:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_jarvis_autostart.ps1
```

The watchdog uses a single instance and a 5-to-60-second restart backoff after
an application failure. Closing JARVIS OS normally also closes the watchdog,
so the application stays off until it is started manually or at the next
Windows sign-in. To remove the scheduled task and stop the watchdog, run the
same script with `-Remove`.

## Repository layout

- `app/` - desktop application and local capabilities
- `cloud_service/` - Azure planner service
- `infra/` - Azure infrastructure definitions
- `tests/` - regression and safety tests
- `tools/` - maintenance and verification utilities
- `data/`, `archive/`, `AI_PLIKI/`, `runtime/` - local runtime state, excluded from Git

## Security

The repository is public. Do not commit passwords, API tokens, OAuth files, private keys, user memory, logs or generated customer packages.
