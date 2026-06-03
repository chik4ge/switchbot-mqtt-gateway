from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import Capability


@dataclass(frozen=True)
class DeviceProfile:
    device_types: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    device_class: type[Any] | None = None

