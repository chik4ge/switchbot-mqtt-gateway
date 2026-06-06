from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

COMMAND_RESULT_CACHE_SIZE = 1000


@dataclass
class GatewayState:
    inventory: dict[str, dict[str, Any]] = field(default_factory=dict)
    seen: dict[str, float] = field(default_factory=dict)
    ble_addresses: dict[str, str] = field(default_factory=dict)
    ble_devices: set[str] = field(default_factory=set)
    normalized_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    latest_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_retained_deletes: dict[str, dict[str, Any]] = field(default_factory=dict)
    command_results: OrderedDict[tuple[str, str], dict[str, Any]] = field(
        default_factory=OrderedDict
    )
    inflight_commands: dict[
        tuple[str, str], asyncio.Task[dict[str, Any]]
    ] = field(default_factory=dict)
