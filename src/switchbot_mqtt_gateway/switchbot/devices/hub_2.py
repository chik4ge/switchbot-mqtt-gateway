from __future__ import annotations

from switchbot_mqtt_gateway.switchbot.capabilities.sensors import (
    HUMIDITY,
    ILLUMINANCE,
    LIGHT_LEVEL,
    RSSI,
    TEMPERATURE,
)
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

HUB_2 = DeviceProfile(
    device_types=("Hub 2",),
    capabilities=(TEMPERATURE, HUMIDITY, ILLUMINANCE, LIGHT_LEVEL, RSSI),
)

