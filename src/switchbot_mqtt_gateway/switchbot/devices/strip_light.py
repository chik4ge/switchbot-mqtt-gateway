from __future__ import annotations

from switchbot.devices.light_strip import SwitchbotLightStrip

from switchbot_mqtt_gateway.switchbot.capabilities.dimmable_light import DIMMABLE_LIGHT
from switchbot_mqtt_gateway.switchbot.capabilities.sensors import RSSI
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

STRIP_LIGHT = DeviceProfile(
    device_types=("Strip Light",),
    capabilities=(DIMMABLE_LIGHT, RSSI),
    device_class=SwitchbotLightStrip,
)

