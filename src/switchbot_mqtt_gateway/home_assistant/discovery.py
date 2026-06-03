from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from switchbot_mqtt_gateway.switchbot.capabilities.base import DiscoveryContext
from switchbot_mqtt_gateway.switchbot.devices.registry import profile_for_device


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "entity"


def discovery_topics_for_device(
    discovery_prefix: str, device_id: str, device: Mapping[str, Any]
) -> list[str]:
    profile = profile_for_device(device)
    if profile is None:
        return []
    topics = []
    for capability in profile.capabilities:
        component = capability.build_component(DiscoveryContext("", device_id))
        if component is not None:
            topics.append(
                f"{discovery_prefix}/{component.component}/{device_id}/{slug(component.object_id)}/config"
            )
    return topics


def build_discovery_configs(
    topic_prefix: str,
    discovery_prefix: str,
    device_id: str,
    device: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    profile = profile_for_device(device)
    if profile is None:
        return []

    name = device.get("deviceName") or device.get("name") or device_id
    model = device.get("deviceType") or device.get("type") or device.get("remoteType") or "SwitchBot"
    device_payload = {
        "identifiers": [f"switchbot_{device_id}"],
        "name": name,
        "manufacturer": "SwitchBot",
        "model": model,
    }
    context = DiscoveryContext(topic_prefix, device_id)
    configs = []
    for capability in profile.capabilities:
        component = capability.build_component(context)
        if component is None:
            continue
        payload = {
            "state_topic": f"{topic_prefix}/devices/{device_id}/state",
            "availability_topic": f"{topic_prefix}/devices/{device_id}/availability",
            "device": device_payload,
            **component.payload,
        }
        topic = f"{discovery_prefix}/{component.component}/{device_id}/{slug(component.object_id)}/config"
        configs.append((topic, payload))
    return configs
