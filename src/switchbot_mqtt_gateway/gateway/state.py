from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayState:
    inventory: dict[str, dict[str, Any]] = field(default_factory=dict)
    seen: dict[str, float] = field(default_factory=dict)
    ble_addresses: dict[str, str] = field(default_factory=dict)
    ble_devices: set[str] = field(default_factory=set)
    command_results: dict[str, dict[str, Any]] = field(default_factory=dict)

