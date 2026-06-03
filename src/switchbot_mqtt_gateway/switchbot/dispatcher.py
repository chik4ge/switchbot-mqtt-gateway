from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile


async def execute_command(
    profile: DeviceProfile,
    device: Any,
    command: Mapping[str, Any],
) -> bool | None:
    action = str(command.get("action") or "")
    handlers = {}
    for capability in profile.capabilities:
        handlers.update(capability.action_handlers())
    handler = handlers.get(action)
    if handler is None:
        raise ValueError("unsupported_action")
    return await handler(device, command)

