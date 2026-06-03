from __future__ import annotations

from switchbot.devices.plug import SwitchbotPlugMini

from switchbot_mqtt_gateway.switchbot.capabilities.power_switch import POWER_SWITCH
from switchbot_mqtt_gateway.switchbot.capabilities.sensors import ACTIVE_POWER, RSSI, WIFI_RSSI
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

PLUG_MINI_JP = DeviceProfile(
    device_types=("Plug Mini (JP)",),
    capabilities=(POWER_SWITCH, ACTIVE_POWER, WIFI_RSSI, RSSI),
    device_class=SwitchbotPlugMini,
)

