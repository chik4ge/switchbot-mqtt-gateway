from __future__ import annotations

from switchbot.devices.ceiling_light import SwitchbotCeilingLight

from switchbot_mqtt_gateway.switchbot.capabilities.color_temperature_light import (
    COLOR_TEMPERATURE_LIGHT,
)
from switchbot_mqtt_gateway.switchbot.capabilities.sensors import RSSI
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

CEILING_LIGHT = DeviceProfile(
    device_types=("Ceiling Light",),
    capabilities=(COLOR_TEMPERATURE_LIGHT, RSSI),
    device_class=SwitchbotCeilingLight,
)

