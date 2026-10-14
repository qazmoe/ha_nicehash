"""Config flow for the nicehash integration (UI setup with validation)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import NiceHashApiError, NiceHashClient
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_ORGANIZATION_ID,
    CONF_CURRENCY,
    CONF_ENABLE_BALANCES,
    CONF_ENABLE_RIGS,
    CONF_ENABLE_DEVICES,
    CONF_ENABLE_PAYOUTS,
    CONF_WATCHED_ALGORITHMS,
    CONF_TRACKED_COINS,
    DEFAULT_CURRENCY,
    DEFAULT_WATCHED_ALGORITHMS,
    DEFAULT_TRACKED_COINS,
    TRACKABLE_COINS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_SECRET): str,
        vol.Required(CONF_ORGANIZATION_ID): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the nicehash_api config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = NiceHashClient(
                user_input[CONF_API_KEY],
                user_input[CONF_API_SECRET],
                user_input[CONF_ORGANIZATION_ID],
            )
            try:
                # live validation before saving anything
                await client.validate_credentials()
            except NiceHashApiError as err:
                _LOGGER.debug("NiceHash credential validation failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                await client.close()
                # check for duplicate entries with same org
                await self.async_set_unique_id(user_input[CONF_ORGANIZATION_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NiceHash {user_input[CONF_ORGANIZATION_ID][:8]}",
                    data=user_input,
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: toggle sensor groups without re-entering credentials."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or {
            CONF_ENABLE_BALANCES: True,
            CONF_ENABLE_RIGS: True,
            CONF_ENABLE_DEVICES: False,
            CONF_ENABLE_PAYOUTS: False,
            CONF_CURRENCY: DEFAULT_CURRENCY,
            CONF_WATCHED_ALGORITHMS: DEFAULT_WATCHED_ALGORITHMS,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_BALANCES, default=current.get(CONF_ENABLE_BALANCES, True)
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_RIGS, default=current.get(CONF_ENABLE_RIGS, True)
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_DEVICES, default=current.get(CONF_ENABLE_DEVICES, False)
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_PAYOUTS, default=current.get(CONF_ENABLE_PAYOUTS, False)
                    ): bool,
                    vol.Optional(
                        CONF_CURRENCY, default=current.get(CONF_CURRENCY, DEFAULT_CURRENCY)
                    ): vol.In(["USD", "EUR", "BTC"]),
                    vol.Optional(
                        CONF_WATCHED_ALGORITHMS,
                        default=current.get(CONF_WATCHED_ALGORITHMS, DEFAULT_WATCHED_ALGORITHMS),
                    ): cv.multi_select({
                        "KHEAVYHASH": "Kaspa (Kheavyhash)",
                        "DAGGERHASHIMOTO": "DaggerHashimoto (ETH-family)",
                        "KAWPOW": "KawPow (Ravencoin)",
                        "SHA256": "SHA256 (BTC)",
                        "RANDOMXMONERO": "RandomX (Monero)",
                        "ETCHASH": "Etchash",
                        "AUTOLYKOS": "Autolykos (Ergo)",
                        "NEXAPOW": "Nexa",
                        "FISHHASH": "FishHash",
                        "EQUIHASH": "Equihash",
                        "BEAMV3": "BeamV3",
                        "ALEPHIUM": "Alephium",
                        "X11": "X11",
                        "EAGLESONG": "Eaglesong (Nervos)",
                        "VERUSHASH": "Verushash",
                        "OCTOPUS": "Octopus (Conflux)",
                    }),
                    vol.Optional(
                        CONF_TRACKED_COINS,
                        default=current.get(CONF_TRACKED_COINS, DEFAULT_TRACKED_COINS),
                    ): cv.multi_select(TRACKABLE_COINS),
                }
            ),
        )
