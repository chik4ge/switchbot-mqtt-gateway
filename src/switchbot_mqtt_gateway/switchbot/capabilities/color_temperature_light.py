from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import ComponentConfig, DiscoveryContext, RawState
from switchbot_mqtt_gateway.switchbot.capabilities.dimmable_light import DIMMABLE_LIGHT
from switchbot_mqtt_gateway.switchbot.parsing import first_value


async def set_color_temperature(device: Any, command: Mapping[str, Any]) -> bool | None:
    value = command.get("value", command.get("color_temperature_kelvin"))
    brightness = command.get("brightness", command.get("brightness_percent", 100))
    if value is None:
        raise ValueError("missing_color_temperature")
    return await device.set_color_temp(int(brightness), int(value))


@dataclass(frozen=True)
class ColorTemperatureLightCapability:
    key: str = "color_temperature_light"

    def normalize(self, *, parsed: RawState, data: RawState, rssi_dbm: int | None) -> dict[str, Any]:
        normalized = DIMMABLE_LIGHT.normalize(parsed=parsed, data=data, rssi_dbm=rssi_dbm)
        value = first_value(data, "cw", "color_temperature_kelvin")
        if value is not None:
            normalized["color_temperature_kelvin"] = value
        return normalized

    def build_component(self, context: DiscoveryContext) -> ComponentConfig:
        component = DIMMABLE_LIGHT.build_component(context)
        component.payload.update(
            {
                "color_temp_kelvin_template": "{{ value_json.normalized.color_temperature_kelvin }}",
                "color_temp_kelvin_command_topic": f"{context.topic_prefix}/devices/{context.device_id}/commands",
                "color_temp_kelvin_command_template": (
                    '{"action":"set_color_temperature","value":{{ value }},'
                    '"brightness":{{ state_attr(entity_id, "brightness") or 100 }}}'
                ),
            }
        )
        return component

    def action_handlers(self) -> Mapping[str, Any]:
        return {
            **DIMMABLE_LIGHT.action_handlers(),
            "set_color_temperature": set_color_temperature,
        }


COLOR_TEMPERATURE_LIGHT = ColorTemperatureLightCapability()
