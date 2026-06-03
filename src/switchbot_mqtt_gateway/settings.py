from __future__ import annotations

import os


class Settings:
    def __init__(self) -> None:
        self.switchbot_api_token = self._required("SWITCHBOT_API_TOKEN")
        self.switchbot_api_secret = self._required("SWITCHBOT_API_SECRET")
        self.mqtt_host = self._required("MQTT_HOST")
        self.mqtt_port = int(self._required("MQTT_PORT"))
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_tls_enabled = os.getenv("MQTT_TLS_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.mqtt_ca_cert_path = os.getenv("MQTT_CA_CERT_PATH") or None
        self.mqtt_client_id = os.getenv("MQTT_CLIENT_ID", "switchbot-mqtt-gateway")
        self.mqtt_keepalive_seconds = int(os.getenv("MQTT_KEEPALIVE_SECONDS", "60"))
        self.topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "switchbot").strip("/")
        self.discovery_prefix = os.getenv("HOME_ASSISTANT_DISCOVERY_PREFIX", "homeassistant").strip("/")
        self.inventory_refresh_seconds = int(
            os.getenv("SWITCHBOT_INVENTORY_REFRESH_INTERVAL_SECONDS", "3600")
        )
        self.device_offline_after_seconds = int(os.getenv("DEVICE_OFFLINE_AFTER_SECONDS", "300"))
        self.log_level = os.getenv("LOG_LEVEL", "info").upper()

    @staticmethod
    def _required(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"missing required environment variable: {name}")
        return value

