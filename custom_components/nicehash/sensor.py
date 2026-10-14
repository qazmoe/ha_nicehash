"""Sensor platform for the nicehash integration."""

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

    # v1.2: coin price sensors (CoinGecko) for tracked coins
    from .const import TRACKABLE_COINS
    for coin in coordinator.data.get("tracked_coins", []):
        label = TRACKABLE_COINS.get(coin, coin.capitalize())
        entities.append(CoinPriceSensor(coordinator, coin, label, "usd"))
        entities.append(CoinPriceSensor(coordinator, coin, label, "btc"))

    async_add_entities(entities)


class NiceHashSensorBase(SensorEntity):
    """Shared base for all nicehash sensors."""

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
        accounts = self._coordinator.data.get("accounts") or {}
        # accounts2 payload: {total: {totalBalance, available, pending (BTC)},
        #                     currencies: [{currency, available, fiatRate...}]}
        if self._currency == "BTC":
            total = accounts.get("total") or {}
            key = {
                "total": "totalBalance",
                "available": "available",
                "pending": "pending",
            }[self._balance_type]
            value = total.get(key)
            return float(value) if value is not None else None
        # fiat: sum holdings in that currency (or convert BTC via fiatRate)
        for c in accounts.get("currencies", []):
            if c.get("currency") == self._currency:
                key = {
                    "total": "balance",
                    "available": "available",
                    "pending": "pending",
                }[self._balance_type]
                value = c.get(key)
                if value is not None:
                    return float(value)
        # fallback: BTC holdings x fiatRate (fiatRate = BTC price in that currency)
        total = accounts.get("total") or {}
        btc = float(total.get("totalBalance") or 0)
        rate = None
        for c in accounts.get("currencies", []):
            if c.get("currency") == self._currency and c.get("fiatRate"):
                rate = float(c["fiatRate"])
                break
        if rate and btc:
            return btc * rate
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


class CoinPriceSensor(NiceHashSensorBase):
    """Spot price of a tracked coin in USD or BTC (CoinGecko)."""

    def __init__(self, coordinator, coin, label, currency):
        super().__init__(coordinator)
        self._coin = coin
        self._currency = currency
        cur_display = "$" if currency == "usd" else "BTC"
        self._attr_name = f"{label} Price ({cur_display})"
        self._attr_unique_id = f"coin:{coin}:price_{currency}"
        if currency == "usd":
            # monetary device_class forbids state_class 'measurement' on prices
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = "USD"
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "BTC"

    @property
    def device_info(self):
        from .const import TRACKABLE_COINS
        return {
            "identifiers": {(DOMAIN, f"coin_{self._coin}")},
            "name": f"NiceHash Coins: {TRACKABLE_COINS.get(self._coin, self._coin)}",
            "manufacturer": "CoinGecko via NiceHash integration",
        }

    @property
    def native_value(self):
        prices = self._coordinator.data.get("coin_prices", {})
        entry = prices.get(self._coin)
        if not entry:
            return None
        value = entry.get(self._currency)
        return float(value) if value is not None else None


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
