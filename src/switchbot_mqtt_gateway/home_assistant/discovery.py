from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntitySpec:
    component: str
    object_id: str
    name: str
    value_template: str
    device_class: str | None = None
    state_class: str | None = None
    unit_of_measurement: str | None = None
    payload_on: str | None = None
    payload_off: str | None = None


COMMON_SPECS = [
    EntitySpec("sensor", "rssi", "RSSI", "{{ value_json.normalized.rssi_dbm }}", "signal_strength", "measurement", "dBm"),
]

DEVICE_TYPE_SPECS: dict[str, list[EntitySpec]] = {
    "MeterPro(CO2)": [
        EntitySpec(
            "sensor",
            "temperature",
            "Temperature",
            "{{ value_json.normalized.temperature_c }}",
            "temperature",
            "measurement",
            "°C",
        ),
        EntitySpec(
            "sensor",
            "humidity",
            "Humidity",
            "{{ value_json.normalized.humidity_percent }}",
            "humidity",
            "measurement",
            "%",
        ),
        EntitySpec(
            "sensor",
            "co2",
            "CO2",
            "{{ value_json.normalized.co2_ppm }}",
            "carbon_dioxide",
            "measurement",
            "ppm",
        ),
    ],
    "Hub 2": [
        EntitySpec(
            "sensor",
            "temperature",
            "Temperature",
            "{{ value_json.normalized.temperature_c }}",
            "temperature",
            "measurement",
            "°C",
        ),
        EntitySpec(
            "sensor",
            "humidity",
            "Humidity",
            "{{ value_json.normalized.humidity_percent }}",
            "humidity",
            "measurement",
            "%",
        ),
        EntitySpec(
            "sensor",
            "illuminance",
            "Illuminance",
            "{{ value_json.normalized.illuminance_lux }}",
            "illuminance",
            "measurement",
            "lx",
        ),
        EntitySpec(
            "sensor",
            "light_level",
            "Light Level",
            "{{ value_json.normalized.light_level }}",
            None,
            "measurement",
            None,
        ),
    ],
    "Plug Mini (JP)": [
        EntitySpec(
            "binary_sensor",
            "power_state",
            "Power State",
            "{{ value_json.normalized.is_on }}",
            "power",
            None,
            None,
            "True",
            "False",
        ),
        EntitySpec(
            "sensor",
            "power",
            "Power",
            "{{ value_json.normalized.power_w }}",
            "power",
            "measurement",
            "W",
        ),
        EntitySpec(
            "sensor",
            "wifi_rssi",
            "Wi-Fi RSSI",
            "{{ value_json.normalized.wifi_rssi_dbm }}",
            "signal_strength",
            "measurement",
            "dBm",
        ),
    ],
    "Strip Light": [
        EntitySpec(
            "binary_sensor",
            "power_state",
            "Power State",
            "{{ value_json.normalized.is_on }}",
            "light",
            None,
            None,
            "True",
            "False",
        ),
        EntitySpec(
            "sensor",
            "brightness",
            "Brightness",
            "{{ value_json.normalized.brightness_percent }}",
            None,
            "measurement",
            "%",
        ),
    ],
    "Ceiling Light": [
        EntitySpec(
            "binary_sensor",
            "power_state",
            "Power State",
            "{{ value_json.normalized.is_on }}",
            "light",
            None,
            None,
            "True",
            "False",
        ),
        EntitySpec(
            "sensor",
            "brightness",
            "Brightness",
            "{{ value_json.normalized.brightness_percent }}",
            None,
            "measurement",
            "%",
        ),
        EntitySpec(
            "sensor",
            "color_temperature",
            "Color Temperature",
            "{{ value_json.pyswitchbot.data.data.cw }}",
            None,
            "measurement",
            None,
        ),
    ],
}


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "entity"


def specs_for_device(device: Mapping[str, Any]) -> list[EntitySpec]:
    device_type = str(device.get("deviceType") or device.get("type") or "")
    return [*DEVICE_TYPE_SPECS.get(device_type, []), *COMMON_SPECS]


def discovery_topics_for_device(
    discovery_prefix: str, device_id: str, device: Mapping[str, Any]
) -> list[str]:
    return [
        f"{discovery_prefix}/{spec.component}/{device_id}/{slug(spec.object_id)}/config"
        for spec in specs_for_device(device)
    ]


def build_discovery_configs(
    topic_prefix: str,
    discovery_prefix: str,
    device_id: str,
    device: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    name = device.get("deviceName") or device.get("name") or device_id
    model = device.get("deviceType") or device.get("type") or device.get("remoteType") or "SwitchBot"
    configs = []
    for spec in specs_for_device(device):
        unique_id = f"switchbot_{device_id}_{slug(spec.object_id)}"
        payload: dict[str, Any] = {
            "name": spec.name,
            "unique_id": unique_id,
            "state_topic": f"{topic_prefix}/devices/{device_id}/state",
            "availability_topic": f"{topic_prefix}/devices/{device_id}/availability",
            "value_template": spec.value_template,
            "device": {
                "identifiers": [f"switchbot_{device_id}"],
                "name": name,
                "manufacturer": "SwitchBot",
                "model": model,
            },
        }
        if spec.device_class:
            payload["device_class"] = spec.device_class
        if spec.state_class:
            payload["state_class"] = spec.state_class
        if spec.unit_of_measurement:
            payload["unit_of_measurement"] = spec.unit_of_measurement
        if spec.payload_on is not None:
            payload["payload_on"] = spec.payload_on
        if spec.payload_off is not None:
            payload["payload_off"] = spec.payload_off

        topic = f"{discovery_prefix}/{spec.component}/{device_id}/{slug(spec.object_id)}/config"
        configs.append((topic, payload))
    return configs
