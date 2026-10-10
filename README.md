# ha_nicehash — NiceHash integration for Home Assistant (maintained)

A from-scratch, config-flow-based NiceHash integration built against the
[NiceHash API v2 docs](https://www.nicehash.com/docs/). Replaces the abandoned
`brianberg/ha-nicehash` line (and its one-commit forks) with a modern
integration that tracks current Home Assistant APIs.

## Why

- The upstream integrations died on removed HA APIs (`Config` import, `HomeAssistantType`, deprecated discovery helpers).
- HA moves faster than NiceHash; an integration we own is a few hundred stable lines instead of a fork chain.
- This repo is actively maintained by the owner's agent (jimbot) — HA deprecations get patched here.

## Features

- **Config flow (UI setup)** — no YAML, no plaintext secrets in configuration.yaml
- **Live credential validation** at setup — bad keys rejected before saving
- **Options flow** — toggle sensor groups (balances / rigs / devices / payouts) and fiat currency without re-entering credentials
- **Sensors**:
  - Account balances: total / available / pending, in BTC and your fiat currency
  - Rig: status, profitability, temperature
  - Per-device (optional): temperature, load
  - Payouts (optional): most recent payout amount
- Coordinated 10-minute polling, graceful degradation (rigs failing doesn't kill balance updates)
- Device registry grouping (rig devices under the NiceHash hub device)

## Installation

### Manual

Copy `custom_components/nicehash_api/` into your Home Assistant
`custom_components/` directory, restart, then:

**Settings → Devices & Services → Add Integration → "NiceHash (maintained)"**

Enter your API key, secret, and organization ID (NiceHash → Settings → API Keys;
the key needs *view* permissions for accounts and mining).

### HACS

Add this repository as a custom repository (category: integration).

## Entity migration from the old integration

Sensors keep the same naming scheme as the legacy integration
(`NiceHash Total Account Balance USD`, `<rig> Status`, etc.) so existing
dashboards keep working after swapping.

## Development

Layout:

- `custom_components/nicehash_api/api.py` — HMAC-signed NiceHash v2 client
- `custom_components/nicehash_api/config_flow.py` — UI setup + credential validation + options flow
- `custom_components/nicehash_api/__init__.py` — DataUpdateCoordinator
- `custom_components/nicehash_api/sensor.py` — sensor platform

## License

MIT
