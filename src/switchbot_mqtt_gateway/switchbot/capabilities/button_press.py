from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import DiscoveryContext


async def press(device: Any, _command: Mapping[str, Any]) -> bool | None:
    return await device.press()


@dataclass(frozen=True)
class ButtonPressCapability:
    key: str = "button_press"

    def normalize(self, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def build_component(self, _context: DiscoveryContext) -> None:
        return None

    def action_handlers(self) -> Mapping[str, Any]:
        return {"press": press}


BUTTON_PRESS = ButtonPressCapability()

