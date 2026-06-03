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


def build_normalized_state(parsed: Mapping[str, Any], rssi_dbm: int | None = None) -> dict[str, Any]:
    data = nested_data(parsed)
    normalized: dict[str, Any] = {}

    model = parsed.get("data", {}).get("modelFriendlyName") if isinstance(parsed.get("data"), Mapping) else None
    model_name = parsed.get("data", {}).get("modelName") if isinstance(parsed.get("data"), Mapping) else None
    if model:
        normalized["model"] = model
    if model_name:
        normalized["model_name"] = model_name

    is_on = first_value(data, "isOn", "is_on")
    if is_on is not None:
        normalized["is_on"] = bool(is_on)

    temperature = first_value(data, "temperature", "temperature_c")
    if temperature is not None:
        normalized["temperature_c"] = temperature

    humidity = first_value(data, "humidity", "humidity_percent")
    if humidity is not None:
        normalized["humidity_percent"] = humidity

    co2 = first_value(data, "co2", "CO2", "co2_ppm")
    if co2 is not None:
        normalized["co2_ppm"] = co2

    illuminance = first_value(data, "illuminance", "illuminance_lux")
    if illuminance is not None:
        normalized["illuminance_lux"] = illuminance

    light_level = first_value(data, "lightLevel", "light_level")
    if light_level is not None:
        normalized["light_level"] = light_level

    brightness = first_value(data, "brightness")
    if brightness is not None:
        normalized["brightness_percent"] = brightness

    power = first_value(data, "power", "power_w")
    if power is not None:
        normalized["power_w"] = power

    wifi_rssi = first_value(data, "wifi_rssi", "wifi_rssi_dbm")
    if wifi_rssi is not None:
        normalized["wifi_rssi_dbm"] = wifi_rssi

    battery = first_value(data, "battery", "battery_percent")
    if battery is not None:
        normalized["battery_percent"] = battery

    sequence_number = first_value(data, "sequence_number")
    if sequence_number is not None:
        normalized["sequence_number"] = sequence_number

    parsed_rssi = parsed.get("rssi")
    if rssi_dbm is not None:
        normalized["rssi_dbm"] = rssi_dbm
    elif parsed_rssi is not None:
        normalized["rssi_dbm"] = parsed_rssi

    return normalized

