from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile
from switchbot_mqtt_gateway.switchbot.parsing import first_value, nested_data


def build_normalized_state(
    profile: DeviceProfile | None,
    parsed: Mapping[str, Any],
    rssi_dbm: int | None = None,
) -> dict[str, Any]:
    data = nested_data(parsed)
    normalized: dict[str, Any] = {}
    root_data = parsed.get("data")

    if isinstance(root_data, Mapping):
        model = root_data.get("modelFriendlyName")
        model_name = root_data.get("modelName")
        if model:
            normalized["model"] = model
        if model_name:
            normalized["model_name"] = model_name

    if profile is not None:
        for capability in profile.capabilities:
            normalized.update(capability.normalize(parsed=parsed, data=data, rssi_dbm=rssi_dbm))

    sequence_number = first_value(data, "sequence_number")
    if sequence_number is not None:
        normalized["sequence_number"] = sequence_number

    return normalized
