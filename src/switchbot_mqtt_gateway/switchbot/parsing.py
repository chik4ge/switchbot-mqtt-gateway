from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def nested_data(parsed: Mapping[str, Any]) -> Mapping[str, Any]:
    data = parsed.get("data")
    if not isinstance(data, Mapping):
        return {}
    inner = data.get("data")
    if not isinstance(inner, Mapping):
        return {}
    return inner


def first_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "on", "1"}:
            return True
        if normalized in {"false", "off", "0"}:
            return False
    return None

