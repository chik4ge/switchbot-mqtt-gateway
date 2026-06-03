from __future__ import annotations

import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from switchbot_mqtt_gateway.utils import log, to_jsonable


def parse_switchbot_advertisement(
    device: BLEDevice, advertisement: AdvertisementData
) -> dict[str, Any] | None:
    try:
        from switchbot.discovery import parse_advertisement_data
    except Exception as exc:
        log("pyswitchbot_import_failed", logging.ERROR, error=str(exc))
        return None
    parsed = parse_advertisement_data(device, advertisement)
    if parsed is None:
        return None
    return to_jsonable(parsed)
