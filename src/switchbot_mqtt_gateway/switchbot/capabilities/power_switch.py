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
from switchbot_mqtt_gateway.switchbot.parsing import first_value, parse_bool


async def set_power(device: Any, command: Mapping[str, Any]) -> bool | None:
    value = str(command.get("value", "")).lower()
    if value == "on":
        return await device.turn_on()
    if value == "off":
        return await device.turn_off()
    raise ValueError("invalid_power_value")


async def turn_on(device: Any, _command: Mapping[str, Any]) -> bool | None:
    return await device.turn_on()


async def turn_off(device: Any, _command: Mapping[str, Any]) -> bool | None:
    return await device.turn_off()


@dataclass(frozen=True)
class PowerSwitchCapability:
    key: str = "power_state"

    def normalize(
        self,
        *,
        parsed: RawState,
        data: RawState,
        rssi_dbm: int | None,
    ) -> NormalizedState:
        value = parse_bool(first_value(data, "isOn", "is_on"))
        if value is None:
            return {}
        return {"is_on": value}

    def build_component(self, context: DiscoveryContext) -> ComponentConfig:
        command_topic = f"{context.topic_prefix}/devices/{context.device_id}/commands"
        return ComponentConfig(
            "switch",
            self.key,
            {
                "platform": "switch",
                "unique_id": f"switchbot_{context.device_id}_{self.key}",
                "name": "Power",
                "value_template": "{{ 'ON' if value_json.normalized.is_on else 'OFF' }}",
                "command_topic": command_topic,
                "payload_on": '{"action":"set_power","value":"on"}',
                "payload_off": '{"action":"set_power","value":"off"}',
                "state_on": "ON",
                "state_off": "OFF",
            },
        )

    def action_handlers(self) -> Mapping[str, Any]:
        return {"set_power": set_power, "power": set_power, "turn_on": turn_on, "turn_off": turn_off}


POWER_SWITCH = PowerSwitchCapability()
