from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any

import paho.mqtt.client as mqtt

from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.utils import json_default, log


class MqttClient:
    def __init__(
        self, settings: Settings, loop: asyncio.AbstractEventLoop, on_reload: Any
    ) -> None:
        self.settings = settings
        self.loop = loop
        self.on_reload = on_reload
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)
        self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.will_set(
            f"{settings.topic_prefix}/gateway/status",
            json.dumps({"status": "offline"}),
            retain=True,
        )
        if settings.mqtt_tls_enabled:
            context = ssl.create_default_context(cafile=settings.mqtt_ca_cert_path)
            self.client.tls_set_context(context)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def connect(self) -> None:
        self.client.connect(
            self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_keepalive_seconds
        )
        self.client.loop_start()

    def stop(self) -> None:
        self.publish("gateway/status", {"status": "offline"}, retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        self.publish_raw(f"{self.settings.topic_prefix}/{topic}", payload, retain=retain)

    def publish_raw(self, topic: str, payload: Any, retain: bool = False) -> None:
        if isinstance(payload, str):
            encoded = payload
        elif payload is None:
            encoded = ""
        else:
            encoded = json.dumps(payload, ensure_ascii=False, default=json_default)
        self.client.publish(topic, encoded, retain=retain)

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: Any, _props: Any) -> None:
        log("mqtt_connected", reason_code=str(rc))
        client.subscribe(f"{self.settings.topic_prefix}/gateway/commands/reload")

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        if message.topic.endswith("/gateway/commands/reload"):
            payload = json.loads(message.payload.decode() or "{}")
            asyncio.run_coroutine_threadsafe(self.on_reload(payload), self.loop)
