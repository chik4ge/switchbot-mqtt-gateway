from __future__ import annotations

import json
import logging
from typing import Any

from switchbot_mqtt_gateway.utils.serialization import json_default

LOGGER = logging.getLogger("switchbot_mqtt_gateway")


def log(event: str, level: int = logging.INFO, **fields: Any) -> None:
    LOGGER.log(level, json.dumps({"event": event, **fields}, ensure_ascii=False, default=json_default))
