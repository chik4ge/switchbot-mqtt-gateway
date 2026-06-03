from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import (
    ComponentConfig,
    DiscoveryContext,
    NormalizedState,
    RawState,
)
from switchbot_mqtt_gateway.switchbot.parsing import first_value


@dataclass(frozen=True)
class SensorCapability:
    key: str
    name: str
    normalized_key: str
    raw_keys: tuple[str, ...]
    device_class: str | None = None
    state_class: str | None = "measurement"
    unit: str | None = None
    entity_category: str | None = None

    def normalize(
        self,
        *,
        parsed: RawState,
        data: RawState,
        rssi_dbm: int | None,
    ) -> NormalizedState:
        if self.normalized_key == "rssi_dbm":
            value = rssi_dbm if rssi_dbm is not None else parsed.get("rssi")
        else:
            value = first_value(data, *self.raw_keys)
        if value is None:
            return {}
        return {self.normalized_key: value}

    def build_component(self, context: DiscoveryContext) -> ComponentConfig:
        payload: dict[str, Any] = {
            "platform": "sensor",
            "unique_id": f"switchbot_{context.device_id}_{self.key}",
            "name": self.name,
            "value_template": f"{{{{ value_json.normalized.{self.normalized_key} }}}}",
        }
        if self.device_class:
            payload["device_class"] = self.device_class
        if self.state_class:
            payload["state_class"] = self.state_class
        if self.unit:
            payload["unit_of_measurement"] = self.unit
        if self.entity_category:
            payload["entity_category"] = self.entity_category
        return ComponentConfig("sensor", self.key, payload)

    def action_handlers(self) -> Mapping[str, Any]:
        return {}


TEMPERATURE = SensorCapability(
    key="temperature",
    name="Temperature",
    normalized_key="temperature_c",
    raw_keys=("temperature", "temperature_c"),
    device_class="temperature",
    unit="°C",
)
HUMIDITY = SensorCapability(
    key="humidity",
    name="Humidity",
    normalized_key="humidity_percent",
    raw_keys=("humidity", "humidity_percent"),
    device_class="humidity",
    unit="%",
)
CO2 = SensorCapability(
    key="co2",
    name="CO2",
    normalized_key="co2_ppm",
    raw_keys=("co2", "CO2", "co2_ppm"),
    device_class="carbon_dioxide",
    unit="ppm",
)
ILLUMINANCE = SensorCapability(
    key="illuminance",
    name="Illuminance",
    normalized_key="illuminance_lux",
    raw_keys=("illuminance", "illuminance_lux"),
    device_class="illuminance",
    unit="lx",
)
LIGHT_LEVEL = SensorCapability(
    key="light_level",
    name="Light Level",
    normalized_key="light_level",
    raw_keys=("lightLevel", "light_level"),
    device_class=None,
    unit=None,
)
ACTIVE_POWER = SensorCapability(
    key="power",
    name="Power",
    normalized_key="power_w",
    raw_keys=("power", "power_w"),
    device_class="power",
    unit="W",
)
WIFI_RSSI = SensorCapability(
    key="wifi_rssi",
    name="Wi-Fi RSSI",
    normalized_key="wifi_rssi_dbm",
    raw_keys=("wifi_rssi", "wifi_rssi_dbm"),
    device_class="signal_strength",
    unit="dBm",
)
BATTERY = SensorCapability(
    key="battery",
    name="Battery",
    normalized_key="battery_percent",
    raw_keys=("battery", "battery_percent"),
    device_class="battery",
    unit="%",
)
BRIGHTNESS = SensorCapability(
    key="brightness",
    name="Brightness",
    normalized_key="brightness_percent",
    raw_keys=("brightness",),
    device_class=None,
    unit="%",
)
RSSI = SensorCapability(
    key="rssi",
    name="RSSI",
    normalized_key="rssi_dbm",
    raw_keys=("rssi",),
    device_class="signal_strength",
    unit="dBm",
    entity_category="diagnostic",
)

