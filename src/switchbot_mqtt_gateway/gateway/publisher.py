from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from switchbot_mqtt_gateway import __version__
from switchbot_mqtt_gateway.home_assistant import (
    build_discovery_configs,
    discovery_topics_for_device,
)
from switchbot_mqtt_gateway.mqtt.client import MqttClient
from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.utils import utc_now


class GatewayPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mqtt: MqttClient | None = None

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        if self.mqtt is not None:
            self.mqtt.publish(topic, payload, retain=retain)

    def publish_absolute(self, topic: str, payload: Any, retain: bool = False) -> None:
        if self.mqtt is not None:
            self.mqtt.publish_raw(topic, payload, retain=retain)

    def publish_gateway_status(self) -> None:
        self.publish(
            "gateway/status",
            {"status": "online", "started_at": utc_now(), "version": __version__},
            retain=True,
        )
        self.publish(
            "gateway/info",
            {"version": __version__, "schema": "pyswitchbot-advertisement-pass-through"},
            retain=True,
        )

    def publish_device_info(self, device_id: str, device: Mapping[str, Any]) -> None:
        self.publish(
            f"devices/{device_id}/info",
            {
                "device_id": device_id,
                "name": device.get("deviceName"),
                "type": device.get("deviceType"),
                "cloud_service_enabled": device.get("enableCloudService"),
                "raw": device,
            },
            retain=True,
        )

    def clear_retained_device_topics(self, device_id: str) -> None:
        self.publish(f"devices/{device_id}/info", None, retain=True)
        self.publish(f"devices/{device_id}/availability", None, retain=True)

    def publish_home_assistant_discovery(
        self, device_id: str, device: Mapping[str, Any]
    ) -> None:
        for topic, payload in build_discovery_configs(
            self.settings.topic_prefix,
            self.settings.discovery_prefix,
            device_id,
            device,
        ):
            self.publish_absolute(topic, payload, retain=True)

    def clear_home_assistant_discovery(
        self, device_id: str, device: Mapping[str, Any]
    ) -> None:
        for topic in discovery_topics_for_device(
            self.settings.discovery_prefix, device_id, device
        ):
            self.publish_absolute(topic, None, retain=True)

