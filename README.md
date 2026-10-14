# ha_nicehash — NiceHash integration for Home Assistant (maintained)

A from-scratch, config-flow-based NiceHash integration built against the
[NiceHash API v2 docs](https://www.nicehash.com/docs/). Replaces the abandoned
`brianberg/ha-nicehash` line (and its one-commit forks) with a modern
integration that tracks current Home Assistant APIs.

## Why

- The upstream integrations died on removed HA APIs (`Config` import, `HomeAssistantType`, deprecated discovery helpers, removed `ConfigEntries` methods).
- HA moves faster than NiceHash; an integration we own is a few hundred stable lines instead of a fork chain.
- This repo is actively maintained — HA deprecations get patched here.

## Features

- **Config flow (UI setup)** — no YAML, no plaintext secrets in configuration.yaml
- **Live credential validation** at setup — bad keys rejected before saving
- **Options flow** — toggle sensor groups and fiat currency without re-entering credentials
- **Sensors**:
  - Account balances: total / available / pending, in BTC and your fiat currency
  - Rig: status, profitability, temperature
  - Per-device (optional): temperature, load
  - Payouts (optional): recent payout + payout history attributes
  - Market (watched algorithms): per-coin paying rate + network hashrate (difficulty proxy) — 16 selectable algorithms including Kaspa, ETH-family, BTC, Monero, Ravencoin
- Coordinated 10-minute polling, graceful degradation (a rigs failure doesn't block balance updates)
- Device registry grouping (rigs and markets under the NiceHash hub device)

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS** (install it first if you haven't: [hacs.xyz](https://hacs.xyz))
2. Go to **HACS → ⚙️ Settings → Custom repositories** (or the "Custom repositories" entry in the HACS three-dot menu)
3. Add this repository:
   - **Repository:** `https://github.com/qazmoe/ha_nicehash`
   - **Category:** **Integration**
4. Click **Add**, then find "NiceHash (maintained)" in HACS and click **Download**
5. **Restart Home Assistant** (HACS will prompt you)
6. Future updates appear automatically in HACS with a red badge on the HACS icon — one click to update

### Manual

Copy `custom_components/nicehash/` from this repo into your Home
Assistant `custom_components/` directory (e.g. `/config/custom_components/`),
restart, then follow the configuration steps below.

## Configuration

Setup is entirely in the UI — **no YAML needed**.

### What you need from NiceHash

Before starting, get your API credentials from NiceHash:

1. Log in at [nicehash.com](https://www.nicehash.com)
2. Go to **Settings → API Keys**
3. Find your **Organization ID** at the top of the API keys page — copy it
4. Click **CREATE NEW API KEY** and when creating the key, grant these permissions:
   - **View accounts** (required — balance sensors)
   - **View mining** (required — rig and market sensors)
   - Withdrawal/funds-management permissions are **NOT needed** — do not grant them
5. Copy the **API Key** and **API Secret** shown at creation time (the secret is displayed once)

### Adding the integration

1. **Settings → Devices & Services → Add Integration**
2. Search for **"NiceHash (maintained)"**
3. Enter:
   - **API Key** — from the step above
   - **API Secret** — from the step above
   - **Organization ID** — from the step above
4. The integration validates your credentials live before saving — if they're
   wrong or missing permissions, you'll get a clear error instead of silent failures
5. On success, your sensors appear within a minute (first data poll)

### Changing options

Click **Configure** on the NiceHash entry in Settings → Devices & Services:

| Option | Controls |
|---|---|
| Account balance sensors | Total/available/pending in BTC + fiat |
| Rig sensors | Status, profitability, temperature per rig |
| Per-device sensors | Temp/load per GPU |
| Payout history sensors | Recent payouts + count |
| Fiat currency | USD / EUR / BTC for balance display |
| Watched algorithms | Which coins get market sensors (multi-select, 16 options) |

Changes apply immediately — no credential re-entry, no restart.

## Entity overview

| Entity pattern | Example |
|---|---|
| `sensor.nicehash_{total,available,pending}_account_balance_{btc,usd}` | `sensor.nicehash_total_account_balance_usd` |
| `sensor.{rig_name}_{status,profitability,temperature}` | `sensor.nb_a100_pnj_status` |
| `sensor.nicehash_market_{algorithm}_{paying_rate,network_hashrate}` | `sensor.nicehash_market_kheavyhash_paying_rate` |
| `sensor.nicehash_recent_mining_payout`, `sensor.nicehash_payout_count` | (when payouts enabled) |

## Development

- **Origin:** [gitea.zlan.io/apps/ha_nicehash](https://gitea.zlan.io/apps/ha_nicehash) (source of truth)
- **This GitHub repo** is the HACS distribution mirror (HACS is GitHub-only)
- Layout:
  - `custom_components/nicehash/api.py` — HMAC-signed NiceHash v2 client
  - `custom_components/nicehash/config_flow.py` — UI setup + credential validation + options flow
  - `custom_components/nicehash/__init__.py` — DataUpdateCoordinator
  - `custom_components/nicehash/sensor.py` — sensor platform
- Release process: bump manifest version → tag `vX.Y.Z` → GitHub release (HACS keys on releases/tags + manifest)

## License

MIT
