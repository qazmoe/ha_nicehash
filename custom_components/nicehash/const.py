"""Constants for the nicehash_api integration."""

from __future__ import annotations

DOMAIN = "nicehash"
NAME = "NiceHash (maintained)"

CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_ORGANIZATION_ID = "organization_id"

# Options-flow keys (sensor group toggles)
CONF_CURRENCY = "currency"
CONF_ENABLE_BALANCES = "enable_balances"
CONF_ENABLE_RIGS = "enable_rigs"
CONF_ENABLE_DEVICES = "enable_devices"
CONF_ENABLE_PAYOUTS = "enable_payouts"

DEFAULT_CURRENCY = "USD"

UPDATE_INTERVAL_MINUTES = 10

# v1.1: market sensors
CONF_WATCHED_ALGORITHMS = "watched_algorithms"
DEFAULT_WATCHED_ALGORITHMS = ["KHEAVYHASH", "DAGGERHASHIMOTO"]

# v1.2: coin tracking (CoinGecko price sensors)
CONF_TRACKED_COINS = "tracked_coins"
DEFAULT_TRACKED_COINS = ["kaspa"]
TRACKABLE_COINS = {"kaspa": "Kaspa (KAS)", "ravencoin": "Ravencoin (RVN)"}

ATTRIBUTION = "Data provided by NiceHash"
