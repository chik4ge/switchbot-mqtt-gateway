from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bleak.backends.device import BLEDevice

from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile
from switchbot_mqtt_gateway.switchbot.devices.bot import BOT
from switchbot_mqtt_gateway.switchbot.devices.ceiling_light import CEILING_LIGHT
from switchbot_mqtt_gateway.switchbot.devices.hub_2 import HUB_2
from switchbot_mqtt_gateway.switchbot.devices.meter_pro_co2 import METER_PRO_CO2
from switchbot_mqtt_gateway.switchbot.devices.plug_mini_jp import PLUG_MINI_JP
from switchbot_mqtt_gateway.switchbot.devices.strip_light import STRIP_LIGHT

PROFILES = (BOT, CEILING_LIGHT, HUB_2, METER_PRO_CO2, PLUG_MINI_JP, STRIP_LIGHT)
DEVICE_TYPE_PROFILES = {
    device_type: profile for profile in PROFILES for device_type in profile.device_types
}


def profile_for_device_type(device_type: str) -> DeviceProfile | None:
    return DEVICE_TYPE_PROFILES.get(device_type)


def profile_for_device(device: Mapping[str, Any]) -> DeviceProfile | None:
    device_type = str(device.get("deviceType") or device.get("type") or "")
    return profile_for_device_type(device_type)


def build_device(profile: DeviceProfile, address: str, name: str | None = None) -> Any:
    if profile.device_class is None:
        raise ValueError("unsupported_device_type")
    return profile.device_class(BLEDevice(address, name, None))

