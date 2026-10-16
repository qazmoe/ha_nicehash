"""The nicehash integration: coordinator + setup."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NiceHashApiError, NiceHashClient
from .const import DOMAIN, UPDATE_INTERVAL_MINUTES, DEFAULT_WATCHED_ALGORITHMS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = NiceHashClient(
        entry.data["api_key"],
        entry.data["api_secret"],
        entry.data["organization_id"],
    )

    async def _update() -> dict[str, Any]:
        data: dict[str, Any] = {
            "rigs": [], "accounts": {}, "payouts": None,
            "market": {}, "market_24h": {}, "simplemultialgo": [],
        }
        try:
            # accounts2 payload: {total: {...BTC totals...}, currencies: [...], ...}
            data["accounts"] = await client.get_accounts()
        except NiceHashApiError as err:
            raise UpdateFailed(f"Error fetching NiceHash accounts: {err}") from err
        try:
            rigs = await client.get_rigs()
            data["rigs"] = rigs.get("miningRigs", [])
            data["total_rigs"] = rigs.get("total", len(data["rigs"]))
        except NiceHashApiError as err:
            _LOGGER.warning("Could not fetch NiceHash rigs: %s", err)
        if entry.options.get("enable_payouts", False):
            try:
                data["payouts"] = await client.get_payouts()
            except NiceHashApiError as err:
                _LOGGER.warning("Could not fetch NiceHash payouts: %s", err)

        # v1.1: market data (public endpoints, no auth cost) — failure is non-fatal
        watched = entry.options.get("watched_algorithms", DEFAULT_WATCHED_ALGORITHMS)
        try:
            current = await client.get_global_stats_current()
            idx = {}
            for algo in current:
                idx[algo.get("a")] = algo
            data["market"] = idx
        except NiceHashApiError as err:
            _LOGGER.warning("Could not fetch NiceHash market stats: %s", err)
        try:
            stats24 = await client.get_global_stats_24h()
            data["market_24h"] = {algo.get("a"): algo for algo in stats24}
        except NiceHashApiError as err:
            _LOGGER.warning("Could not fetch 24h market stats: %s", err)
        try:
            sma = await client.get_simplemultialgo()
            data["simplemultialgo"] = [a for a in sma if a.get("algorithm") in watched]
        except NiceHashApiError as err:
            _LOGGER.warning("Could not fetch simplemultialgo: %s", err)
        data["watched_algorithms"] = watched

        # v1.2: coin prices (CoinGecko, unauthenticated) for the tracked coins
        tracked_coins = [c.lower() for c in entry.options.get("tracked_coins", ["kaspa"])]
        try:
            data["coin_prices"] = await client.get_coin_prices(tracked_coins)
        except Exception as err:  # CoinGecko is external; never block the coordinator
            _LOGGER.warning("Could not fetch coin prices: %s", err)
        # v1.4: network difficulty per tracked coin (explorer APIs, best-effort)
        data["coin_difficulty"] = {}
        for coin in tracked_coins:
            try:
                diff = await client.get_coin_difficulty(coin)
                if diff is not None:
                    data["coin_difficulty"][coin] = diff
            except Exception as err:
                _LOGGER.warning("Could not fetch %s difficulty: %s", coin, err)
        data["tracked_coins"] = tracked_coins
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"nicehash_{entry.data['organization_id'][:8]}",
        update_method=_update,
        update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        store = hass.data[DOMAIN].pop(entry.entry_id)
        await store["client"].close()
    return unload_ok
