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
                "command_on_template": '{"action":"set_power","value":"on"}',
                "command_off_template": '{"action":"set_power","value":"off"}',
                "state_template": "{{ 'on' if value_json.normalized.is_on else 'off' }}",
                "brightness_template": "{{ value_json.normalized.brightness_percent }}",
                "brightness_command_topic": command_topic,
                "brightness_command_template": '{"action":"set_brightness","value":{{ value }}}',
            },
        )

    def action_handlers(self) -> Mapping[str, Any]:
        return {**POWER_SWITCH.action_handlers(), "set_brightness": set_brightness}


DIMMABLE_LIGHT = DimmableLightCapability()
