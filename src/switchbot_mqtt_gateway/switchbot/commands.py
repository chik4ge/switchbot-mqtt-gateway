from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bleak.backends.device import BLEDevice
from switchbot.devices.bot import Switchbot
from switchbot.devices.ceiling_light import SwitchbotCeilingLight
from switchbot.devices.light_strip import SwitchbotLightStrip
from switchbot.devices.plug import SwitchbotPlugMini


DEVICE_CLASSES = {
    "Bot": Switchbot,
    "Ceiling Light": SwitchbotCeilingLight,
    "Plug Mini (JP)": SwitchbotPlugMini,
    "Strip Light": SwitchbotLightStrip,
}


def build_device(device_type: str, address: str, name: str | None = None) -> Any:
    device_class = DEVICE_CLASSES.get(device_type)
    if device_class is None:
        raise ValueError(f"unsupported_device_type:{device_type}")
    return device_class(BLEDevice(address, name, None))


async def execute_command(device: Any, command: Mapping[str, Any]) -> bool | None:
    action = command.get("action")
    if action in {"set_power", "power"}:
        value = str(command.get("value", "")).lower()
        if value == "on":
            return await device.turn_on()
        if value == "off":
            return await device.turn_off()
        raise ValueError("invalid_power_value")
    if action == "turn_on":
        return await device.turn_on()
    if action == "turn_off":
        return await device.turn_off()
    if action == "press":
        return await device.press()
    if action == "set_brightness":
        value = command.get("value", command.get("brightness"))
        if value is None:
            raise ValueError("missing_brightness")
        return await device.set_brightness(int(value))
    raise ValueError("unsupported_action")

