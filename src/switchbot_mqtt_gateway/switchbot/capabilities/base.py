from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

RawState = Mapping[str, Any]
NormalizedState = dict[str, Any]
ActionHandler = Callable[[Any, Mapping[str, Any]], Awaitable[bool | None]]


@dataclass(frozen=True)
class DiscoveryContext:
    topic_prefix: str
    device_id: str


@dataclass(frozen=True)
class ComponentConfig:
    component: str
    object_id: str
    payload: dict[str, Any]


class Capability(Protocol):
    key: str

    def normalize(
        self,
        *,
        parsed: RawState,
        data: RawState,
        rssi_dbm: int | None,
    ) -> NormalizedState:
        ...

    def build_component(self, context: DiscoveryContext) -> ComponentConfig | None:
        ...

    def action_handlers(self) -> Mapping[str, ActionHandler]:
        ...


def no_normalized_state() -> NormalizedState:
    return {}

