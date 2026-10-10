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
        entities.append(PayoutHistorySensor(coordinator, org_id))

    # v1.1: market sensors for watched algorithms
    for algo_info in coordinator.data.get("simplemultialgo", []):
        algo = algo_info.get("algorithm", "")
        entities.append(AlgorithmPayingSensor(coordinator, algo, algo_info.get("title", algo)))
        entities.append(AlgorithmNetworkSpeedSensor(coordinator, algo, algo_info.get("title", algo)))

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
    # monetary device_class requires state_class 'total' (or None); balances are totals, not measurements
    _attr_state_class = SensorStateClass.TOTAL

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


class PayoutHistorySensor(NiceHashSensorBase):
    """Cumulative payout count over the fetched window + recent list as attributes."""

    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, org_id):
        super().__init__(coordinator)
        self._attr_name = "NiceHash Payout Count (window)"
        self._attr_unique_id = f"{org_id}:payout_count"
        self._attr_native_unit_of_measurement = "payouts"

    @property
    def native_value(self):
        payouts = self._coordinator.data.get("payouts")
        if not payouts:
            return None
        return len(payouts.get("list", []))

    @property
    def extra_state_attributes(self):
        payouts = self._coordinator.data.get("payouts")
        if not payouts:
            return None
        listing = payouts.get("list", [])[:10]
        return {
            "payouts": [
                {
                    "created": p.get("created"),
                    "amount": p.get("amount"),
                    "fee": p.get("feeAmount"),
                }
                for p in listing
            ],
            "total": payouts.get("total"),
        }


class AlgorithmMarketSensorBase(NiceHashSensorBase):
    def __init__(self, coordinator, algorithm: str, title: str) -> None:
        super().__init__(coordinator)
        self._algorithm = algorithm
        self._title = title

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"market_{self._algorithm}")},
            "name": f"NiceHash Market: {self._title}",
            "manufacturer": "NiceHash",
        }

    def _sma_entry(self):
        for a in self._coordinator.data.get("simplemultialgo", []):
            if a.get("algorithm") == self._algorithm:
                return a
        return None


class AlgorithmPayingSensor(AlgorithmMarketSensorBase):
    """Current paying rate for a watched algorithm (BTC per unit per day)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:currency-btc"

    def __init__(self, coordinator, algorithm, title):
        super().__init__(coordinator, algorithm, title)
        self._attr_name = f"{title} Paying Rate"
        self._attr_unique_id = f"market:{algorithm}:paying"
        self._attr_native_unit_of_measurement = "BTC/TH/day"

    @property
    def native_value(self):
        entry = self._sma_entry()
        if entry is None:
            return None
        paying = entry.get("paying")
        return float(paying) if paying else None

    @property
    def extra_state_attributes(self):
        entry = self._sma_entry()
        if not entry:
            return None
        speed = entry.get("speed")
        return {"network_speed": float(speed) if speed else None}


class AlgorithmNetworkSpeedSensor(AlgorithmMarketSensorBase):
    """Total network hashrate for a watched algorithm (difficulty proxy)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator, algorithm, title):
        super().__init__(coordinator, algorithm, title)
        self._attr_name = f"{title} Network Hashrate"
        self._attr_unique_id = f"market:{algorithm}:speed"
        self._attr_native_unit_of_measurement = "H/s"

    @property
    def native_value(self):
        entry = self._sma_entry()
        if entry is None:
            return None
        speed = entry.get("speed")
        return float(speed) if speed else None


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
