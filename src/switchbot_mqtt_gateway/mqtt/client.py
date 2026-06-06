from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import ssl
from typing import Any

import paho.mqtt.client as mqtt

from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.utils import json_default, log


class MqttClient:
    def __init__(
        self,
        settings: Settings,
        loop: asyncio.AbstractEventLoop,
        on_reload: Any,
        on_command: Any,
        on_reconnect: Any,
    ) -> None:
        self.settings = settings
        self.loop = loop
        self.on_reload = on_reload
        self.on_command = on_command
        self.on_reconnect = on_reconnect
        self.connected = asyncio.Event()
        self._has_connected = False
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
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        self.client.connect_async(
            self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_keepalive_seconds
        )
        self.client.loop_start()

    def stop(self) -> None:
        try:
            message = self.publish("gateway/status", {"status": "offline"}, retain=True)
            message.wait_for_publish(timeout=2.0)
        except RuntimeError as exc:
            log("mqtt_offline_publish_failed", logging.WARNING, error=str(exc))
        finally:
            self.client.disconnect()
            self.client.loop_stop()

    async def wait_until_connected(self) -> None:
        await self.connected.wait()

    def publish(self, topic: str, payload: Any, retain: bool = False) -> mqtt.MQTTMessageInfo:
        return self.publish_raw(f"{self.settings.topic_prefix}/{topic}", payload, retain=retain)

    def publish_raw(
        self, topic: str, payload: Any, retain: bool = False
    ) -> mqtt.MQTTMessageInfo:
        if isinstance(payload, str):
            encoded = payload
        elif payload is None:
            encoded = ""
        else:
            encoded = json.dumps(payload, ensure_ascii=False, default=json_default)
        return self.client.publish(topic, encoded, retain=retain)

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: Any, _props: Any) -> None:
        if int(rc) != 0:
            log("mqtt_connect_failed", logging.ERROR, reason_code=str(rc))
            return
        log("mqtt_connected", reason_code=str(rc))
        client.subscribe(f"{self.settings.topic_prefix}/gateway/commands/reload")
        client.subscribe(f"{self.settings.topic_prefix}/devices/+/commands")
        self.loop.call_soon_threadsafe(self.connected.set)
        if self._has_connected:
            self._submit(self.on_reconnect(), "mqtt/reconnect")
        else:
            self._has_connected = True

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log("invalid_mqtt_payload", logging.WARNING, topic=message.topic, error=str(exc))
            return
        if not isinstance(payload, dict):
            log("invalid_mqtt_payload_type", logging.WARNING, topic=message.topic)
            return

        if message.topic.endswith("/gateway/commands/reload"):
            self._submit(self.on_reload(payload), message.topic)
            return
        prefix = f"{self.settings.topic_prefix}/devices/"
        if message.topic.startswith(prefix) and message.topic.endswith("/commands"):
            device_id = message.topic.removeprefix(prefix).removesuffix("/commands")
            self._submit(self.on_command(device_id, payload), message.topic)

    def _submit(self, coroutine: Any, topic: str) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        future.add_done_callback(lambda completed: self._log_handler_error(completed, topic))

    @staticmethod
    def _log_handler_error(future: concurrent.futures.Future[Any], topic: str) -> None:
        try:
            future.result()
        except Exception as exc:
            log("mqtt_handler_failed", logging.ERROR, topic=topic, error=str(exc))
