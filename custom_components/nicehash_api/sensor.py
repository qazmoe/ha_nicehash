"""Sensor platform for the nicehash_api integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    org_id = entry.data["organization_id"]
    opts = entry.options or {}

    entities: list[SensorEntity] = []

    # Rigs (and their device sensors when enabled)
    rigs = coordinator.data.get("rigs", [])
    for rig in rigs:
        rig_id = rig.get("rigId", "")
        rig_name = rig.get("name", rig_id)
        entities.append(RigStatusSensor(coordinator, rig_id, rig_name))
        entities.append(RigProfitabilitySensor(coordinator, rig_id, rig_name))
        entities.append(RigTemperatureSensor(coordinator, rig_id, rig_name))
        if opts.get("enable_devices", False):
            for device in rig.get("devices", []) or []:
                dev_id = device.get("id", "")
                dev_name = device.get("name", dev_id)
                entities.append(DeviceTemperatureSensor(coordinator, rig_id, dev_id, dev_name))
                entities.append(DeviceLoadSensor(coordinator, rig_id, dev_id, dev_name))

    # Balances (BTC + selected fiat)
    if opts.get("enable_balances", True):
        currency = opts.get("currency", "USD")
        for balance_type in ("total", "available", "pending"):
            entities.append(
                BalanceSensor(coordinator, org_id, currency, balance_type)
            )
        for balance_type in ("total", "available", "pending"):
            entities.append(
                BalanceSensor(coordinator, org_id, "BTC", balance_type)
            )

    # Payouts
    if opts.get("enable_payouts", False):
        entities.append(RecentPayoutSensor(coordinator, org_id))

    async_add_entities(entities)


class NiceHashSensorBase(SensorEntity):
    """Shared base for all nicehash_api sensors."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator
        self._attr_should_poll = False
        coordinator.async_add_listener(self._handle_update)

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "nicehash")},
            "name": "NiceHash",
            "manufacturer": "NiceHash",
        }


def _find_rig(coordinator, rig_id: str) -> dict[str, Any] | None:
    for rig in coordinator.data.get("rigs", []):
        if rig.get("rigId") == rig_id:
            return rig
    return None


def _rig_device(coordinator, rig_id: str, device_id: str) -> dict[str, Any] | None:
    rig = _find_rig(coordinator, rig_id)
    for device in (rig or {}).get("devices", []) or []:
        if device.get("id") == device_id:
            return device
    return None


class RigSensorBase(NiceHashSensorBase):
    def __init__(self, coordinator, rig_id: str, rig_name: str) -> None:
        super().__init__(coordinator)
        self._rig_id = rig_id
        self._rig_name = rig_name

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._rig_id)},
            "name": self._rig_name,
            "manufacturer": "NiceHash",
            "via_device": (DOMAIN, "nicehash"),
        }


class RigStatusSensor(RigSensorBase):
    _attr_icon = "mdi:excavator"

    def __init__(self, coordinator, rig_id, rig_name):
        super().__init__(coordinator, rig_id, rig_name)
        self._attr_name = f"{rig_name} Status"
        self._attr_unique_id = f"{rig_id}:status"

    @property
    def native_value(self):
        rig = _find_rig(self._coordinator, self._rig_id)
        if rig is None:
            return None
        status = rig.get("minerStatus")
        return str(status).upper() if status else None


class RigProfitabilitySensor(RigSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, rig_id, rig_name):
        super().__init__(coordinator, rig_id, rig_name)
        self._attr_name = f"{rig_name} Profitability"
        self._attr_unique_id = f"{rig_id}:profitability"
        self._attr_native_unit_of_measurement = "USD/day"

    @property
    def native_value(self):
        rig = _find_rig(self._coordinator, self._rig_id)
        if rig is None:
            return None
        return float(rig["profitability"]) if rig.get("profitability") else None


class RigTemperatureSensor(RigSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator, rig_id, rig_name):
        super().__init__(coordinator, rig_id, rig_name)
        self._attr_name = f"{rig_name} Temperature"
        self._attr_unique_id = f"{rig_id}:high_temperature"

    @property
    def native_value(self):
        rig = _find_rig(self._coordinator, self._rig_id)
        if rig is None:
            return None
        return rig.get("highTemperature")


class DeviceTemperatureSensor(RigSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator, rig_id, dev_id, dev_name):
        super().__init__(coordinator, rig_id, dev_name)
        self._dev_id = dev_id
        self._attr_name = f"{dev_name} Temperature"
        self._attr_unique_id = f"{rig_id}:{dev_id}:temperature"

    @property
    def native_value(self):
        device = _rig_device(self._coordinator, self._rig_id, self._dev_id)
        return (device or {}).get("temperature")


class DeviceLoadSensor(RigSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:memory"

    def __init__(self, coordinator, rig_id, dev_id, dev_name):
        super().__init__(coordinator, rig_id, dev_name)
        self._dev_id = dev_id
        self._attr_name = f"{dev_name} Load"
        self._attr_unique_id = f"{rig_id}:{dev_id}:load"

    @property
    def native_value(self):
        device = _rig_device(self._coordinator, self._rig_id, self._dev_id)
        return (device or {}).get("load")


class BalanceSensor(NiceHashSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, org_id, currency, balance_type):
        super().__init__(coordinator)
        self._org_id = org_id
        self._currency = currency
        self._balance_type = balance_type
        self._attr_name = f"NiceHash {balance_type.capitalize()} Account Balance {currency}"
        self._attr_unique_id = f"{org_id}:{currency}:{balance_type}"
        if currency == "BTC":
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = "BTC"
        else:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = currency

    @property
    def native_value(self):
        for account in self._coordinator.data.get("accounts", []):
            if account.get("currency") == self._currency:
                key = {
                    "total": "totalBalance",
                    "available": "availableBalance",
                    "pending": "pendingBalance",
                }[self._balance_type]
                value = account.get(key)
                return float(value) if value is not None else None
        return None


class RecentPayoutSensor(NiceHashSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash-refund"

    def __init__(self, coordinator, org_id):
        super().__init__(coordinator)
        self._attr_name = "NiceHash Recent Mining Payout"
        self._attr_unique_id = f"{org_id}:recent_payout"
        self._attr_native_unit_of_measurement = "BTC"

    @property
    def native_value(self):
        payouts = self._coordinator.data.get("payouts")
        if not payouts:
            return None
        payout_list = payouts.get("list", [])
        if not payout_list:
            return None
        return float(payout_list[0].get("amount", 0))
