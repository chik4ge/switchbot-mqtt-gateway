from __future__ import annotations

import dataclasses
import json
from typing import Any


def json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, bytearray):
        return bytes(value).hex()
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def to_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=json_default, ensure_ascii=False))

