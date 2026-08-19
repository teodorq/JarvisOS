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
- MetaTrader 5 desktop and its official Python package are optional for Forex PAPER data

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

## Local paper-trading foundation

JARVIS OS includes an owner-only, broker-neutral trading foundation for safe
simulation and research. It provides strict market models, conservative
pre-trade limits, an atomic local demo ledger, a tamper-evident audit chain, an
emergency stop and next-bar historical backtesting. Optional read-only market
data can feed the simulator, but there is no broker order connection, leverage
or path to real-money orders.

Historical research also supports a strict chronological holdout and rolling
walk-forward validation. Every test period follows its training period, future
test windows cannot overlap, fills still occur only on a later bar, and neither
result can automatically promote PAPER or send an order. The validator does not
claim to audit how external signals were generated; that remains a separate
anti-look-ahead requirement for every strategy adapter.

Say or type `Status paper tradingu` in owner mode to see the local readiness
snapshot. The feature is blocked in client mode. Detailed scope, limits and the
required gates before any future broker integration are documented in
[`TRADING_READINESS.md`](TRADING_READINESS.md). Paper results do not predict
live-market performance; this module is technical research infrastructure, not
investment advice.

The Forex PAPER layer scans seven major currency pairs, ranks deterministic
signals and applies portfolio-wide currency exposure limits. A local autonomous
cycle can open or close simulated positions, recheck risk at execution time,
persist an audit trail and reject duplicate cycles. The primary source can be a
local MetaTrader 5 terminal logged into a DEMO account; an OANDA Practice REST
adapter remains an alternative for regions where v20 is available. Twelve Data
cross-checks prices, NBP supplies the public USD/PLN reference and the public
weekly Forex Factory export supplies the economic calendar. Configuration is
absent by default, so the opening gate remains closed. No broker order route or
continuous background feed is exposed.

Before PAPER execution is enabled, use the observation-only cycle. It reads all
configured sources, calculates the same assessment and proposed plan, then stops
before the execution boundary. Evidence is kept in the ignored, tamper-evident
`data/trading/forex_observations.json` journal and never promotes itself:

```powershell
.\.venv\Scripts\python.exe .\tools\run_forex_observation.py
.\.venv\Scripts\python.exe .\tools\run_forex_observation.py --status
```

On Windows, install the observation-only autostart once:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\install_forex_observer_autostart.ps1
```

The limited interactive task starts only the configured OANDA TMS MT5 terminal,
waits for it to connect and records an observation every 15 minutes while the
Forex market is open. It opens no web pages and exposes no order route. Remove
the task with the same command plus `-Remove`.

In owner mode, say or type `Ile obserwacji Forex?`,
`Status obserwatora Forex` or `Czy PAPER jest gotowy?`. JARVIS reads the local
tamper-evident journal and reports qualified observations, distinct market days,
the remaining gate and whether PAPER execution is actually enabled. The status
loads the ignored `config/forex.env` through the allowlisted loader but never
shows a key or token.

Use `Raport obserwacji Forex` for a deeper read-only review. It aggregates every
recorded cycle, market-day coverage, blocked reasons, proposed but unexecuted
actions, all seven-pair coverage and order-safety invariants. The report cannot
promote or enable PAPER or LIVE execution.

## Optional Forex PAPER data

For OANDA TMS in Poland, install its Windows MetaTrader 5, sign the terminal in
to a DEMO account and install the optional local package:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_trading_mt5.txt
```

JARVIS does not store the MT5 login or password. It uses the terminal's current
session and rejects real and contest accounts before reading the first price.

Export a local research snapshot of 5,000 closed M15 bars for all seven pairs:

```powershell
.\.venv\Scripts\python.exe .\tools\export_mt5_history.py --bars 5000
.\.venv\Scripts\python.exe .\tools\export_mt5_history.py --verify-latest
```

The export is stored under ignored `data/trading/history/`. Every pair gets a
validated CSV and SHA-256 fingerprint in a secret-free manifest. Verification
re-reads every CSV and fails if a file, fingerprint, pair set or safety flag has
changed. It also checks timestamp alignment across pairs, positive tick volume
and distinguishes regular weekend closures from unexpected intraday gaps. MT5
position zero is the current bar, so the adapter deliberately starts at position
one and exports closed bars only.

Run the fixed LONG/SHORT 10/30 moving-average research on the newest verified
export:

```powershell
.\.venv\Scripts\python.exe .\tools\run_forex_historical_research.py
```

The test generates every signal from current and earlier closed bars and fills
it only at the next M15 open. It uses isolated chronological walk-forward
windows plus a conservative synthetic spread/slippage model. Results remain
separate in each pair's quote currency because the export does not contain a
complete historical PLN conversion series. The ignored detailed report is
written to `data/trading/research/latest.json`. This command cannot connect to
the broker or promote PAPER/LIVE trading, and its results are research rather
than a prediction of future profit.
Then copy `config/forex.env.example` to the ignored `config/forex.env` and fill
in:

- a Twelve Data API key for the independent price check;
- the public weekly Forex Factory economic calendar needs no key.

On Windows, copy one key to the clipboard and store it without placing the
secret in shell history:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\set_local_forex_secret.ps1 -Name JARVIS_OS_TWELVE_DATA_API_KEY
```

The helper writes the ignored file and removes the secret from the clipboard.

Keep `JARVIS_OS_FOREX_PRIMARY_PROVIDER=MT5_DEMO` and, for OANDA TMS,
`JARVIS_OS_MT5_SYMBOL_SUFFIX=.pro`. The optional
`OANDA_PRACTICE` provider is retained for non-TMS divisions with REST-v20
Practice access and requires its separate practice account ID and token.

NBP and Forex Factory need no keys. Secrets are sent in HTTPS headers and
excluded from status
and object representations, and are never committed. A cycle requires all
seven primary quotes, 31 completed M15 candles per pair, matching fresh prices
from the second source, a fresh calendar and a sufficiently recent NBP
reference. Missing, stale or divergent data blocks new positions. The MT5
adapter requests only current ticks and already-closed M15 bars; it contains no
method for placing, changing or closing broker orders.

## Optional Google Workspace integration

Copy `config/google_workspace_client_secret.example.json` to a local credentials file and fill it with credentials from Google Cloud. Real client secrets and OAuth tokens must never be committed.

## Weather without an API key

JARVIS OS can answer `Jaka jest pogoda w Miami?` and
`Jaka bedzie pogoda jutro w Warszawie?` through a direct, read-only Open-Meteo
lookup. The fixed HTTPS endpoints use bounded responses and short timeouts; no
account or API key is required. Location text is used only for the lookup and is
not written to a separate weather history. The response identifies Open-Meteo
as its source.

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

Say or type `Co potrafisz?` (or use `CO POTRAFIĘ` in the daily tools) for a
short, client-safe guide with verified example commands. The guide performs no
action and never advertises owner-only development or business controls.

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
