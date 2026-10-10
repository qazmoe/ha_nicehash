"""The nicehash_api integration: coordinator + setup."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NiceHashApiError, NiceHashClient
from .const import DOMAIN, UPDATE_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = NiceHashClient(
        entry.data["api_key"],
        entry.data["api_secret"],
        entry.data["organization_id"],
    )

    async def _update() -> dict[str, Any]:
        data: dict[str, Any] = {"rigs": [], "accounts": [], "payouts": None}
        try:
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
    await hass.config_entries.async_forward_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        store = hass.data[DOMAIN].pop(entry.entry_id)
        await store["client"].close()
    return unload_ok
