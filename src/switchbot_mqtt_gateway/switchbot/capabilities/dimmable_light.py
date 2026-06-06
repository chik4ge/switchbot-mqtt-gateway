from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import ComponentConfig, DiscoveryContext
from switchbot_mqtt_gateway.switchbot.capabilities.power_switch import POWER_SWITCH
from switchbot_mqtt_gateway.switchbot.capabilities.sensors import BRIGHTNESS


async def set_brightness(device: Any, command: Mapping[str, Any]) -> bool | None:
    value = command.get("value", command.get("brightness"))
    if value is None:
        raise ValueError("missing_brightness")
    return await device.set_brightness(int(value))


async def set_light(device: Any, command: Mapping[str, Any]) -> bool | None:
    state = str(command.get("state") or "").lower()
    if state == "off":
        return await device.turn_off()
    if state not in {"", "on"}:
        raise ValueError("invalid_power_value")

    result = await device.turn_on()
    brightness = command.get("brightness")
    if brightness is not None:
        result = await device.set_brightness(max(0, min(100, round(int(brightness) * 100 / 255))))
    return result


@dataclass(frozen=True)
class DimmableLightCapability:
    key: str = "dimmable_light"

    def normalize(self, **kwargs: Any) -> dict[str, Any]:
        return {**POWER_SWITCH.normalize(**kwargs), **BRIGHTNESS.normalize(**kwargs)}

    def build_component(self, context: DiscoveryContext) -> ComponentConfig:
        command_topic = f"{context.topic_prefix}/devices/{context.device_id}/commands"
        return ComponentConfig(
            "light",
            "light",
            {
                "platform": "light",
                "unique_id": f"switchbot_{context.device_id}_light",
                "name": "Light",
                "schema": "template",
                "command_topic": command_topic,
                "command_on_template": (
                    '{"action":"set_light","state":"on"'
                    '{% if brightness is defined %},"brightness":{{ brightness }}{% endif %}}'
                ),
                "command_off_template": '{"action":"set_light","state":"off"}',
                "state_template": "{{ 'on' if value_json.normalized.is_on else 'off' }}",
                "brightness_template": (
                    "{{ (value_json.normalized.brightness_percent | float * 255 / 100) | round(0) }}"
                ),
            },
        )

    def action_handlers(self) -> Mapping[str, Any]:
        return {
            **POWER_SWITCH.action_handlers(),
            "set_brightness": set_brightness,
            "set_light": set_light,
        }


DIMMABLE_LIGHT = DimmableLightCapability()
