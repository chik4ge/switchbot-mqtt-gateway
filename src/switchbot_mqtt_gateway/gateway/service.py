from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from switchbot_mqtt_gateway import __version__
from switchbot_mqtt_gateway.home_assistant import (
    build_discovery_configs,
    discovery_topics_for_device,
)
from switchbot_mqtt_gateway.switchbot.ble import parse_switchbot_advertisement
from switchbot_mqtt_gateway.mqtt.client import MqttClient
from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.switchbot.openapi import SwitchBotOpenApi
from switchbot_mqtt_gateway.utils import log, utc_now


class Gateway:
    def __init__(self, settings: Settings, api: SwitchBotOpenApi | None = None) -> None:
        self.settings = settings
        self.api = api or SwitchBotOpenApi(settings)
        self.inventory: dict[str, dict[str, Any]] = {}
        self.seen: dict[str, float] = {}
        self.ble_devices: set[str] = set()
        self.mqtt: MqttClient | None = None

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.mqtt = MqttClient(self.settings, loop, self.reload)
        self.mqtt.connect()
        self.publish_gateway_status()
        await self.refresh_inventory()
        scanner = BleakScanner(detection_callback=self.on_advertisement)
        await scanner.start()
        log("ble_scan_started")
        try:
            await asyncio.gather(self.periodic_inventory_refresh(), self.periodic_availability())
        finally:
            await scanner.stop()
            self.mqtt.stop()

    async def reload(self, payload: Mapping[str, Any]) -> None:
        before = dict(self.inventory)
        await self.refresh_inventory()
        added = self.inventory.keys() - before.keys()
        removed = before.keys() - self.inventory.keys()
        updated = {
            device_id
            for device_id in self.inventory.keys() & before.keys()
            if self.inventory[device_id] != before[device_id]
        }
        self.mqtt_publish(
            "gateway/events/reload_result",
            {
                "request_id": payload.get("request_id"),
                "status": "succeeded",
                "devices_total": len(self.inventory),
                "devices_added": len(added),
                "devices_updated": len(updated),
                "devices_removed": len(removed),
                "completed_at": utc_now(),
            },
        )

    async def periodic_inventory_refresh(self) -> None:
        while True:
            await asyncio.sleep(self.settings.inventory_refresh_seconds)
            try:
                await self.refresh_inventory()
            except Exception as exc:
                log("inventory_refresh_failed", logging.ERROR, error=str(exc))

    async def periodic_availability(self) -> None:
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for device_id in self.ble_devices:
                last_seen = self.seen.get(device_id)
                if last_seen is None or now - last_seen > self.settings.device_offline_after_seconds:
                    self.mqtt_publish(f"devices/{device_id}/availability", "offline", retain=True)

    async def refresh_inventory(self) -> None:
        devices = await self.api.fetch_devices()
        before = self.inventory
        removed = before.keys() - devices.keys()
        self.inventory = devices
        self.publish_inventory()
        for device_id, device in devices.items():
            if device_id in self.ble_devices:
                self.publish_device_info(device_id, device)
                self.publish_home_assistant_discovery(device_id, device)
            else:
                self.clear_retained_device_topics(device_id)
                self.clear_home_assistant_discovery(device_id, device)
        for device_id in removed & self.ble_devices:
            self.mqtt_publish(f"devices/{device_id}/availability", "offline", retain=True)
            self.clear_retained_device_topics(device_id)
            self.clear_home_assistant_discovery(device_id, before[device_id])
        log("inventory_refreshed", devices_total=len(devices), devices_removed=len(removed))

    def publish_gateway_status(self) -> None:
        self.mqtt_publish(
            "gateway/status",
            {"status": "online", "started_at": utc_now(), "version": __version__},
            retain=True,
        )
        self.mqtt_publish(
            "gateway/info",
            {"version": __version__, "schema": "pyswitchbot-advertisement-pass-through"},
            retain=True,
        )

    def publish_inventory(self) -> None:
        visible_devices = self.ble_devices & self.inventory.keys()
        self.mqtt_publish(
            "gateway/inventory",
            {
                "refreshed_at": utc_now(),
                "devices_total": len(self.inventory),
                "ble_devices_total": len(self.ble_devices),
                "published_devices_total": len(visible_devices),
                "devices": [
                    {
                        "device_id": device_id,
                        "name": device.get("deviceName"),
                        "type": device.get("deviceType"),
                        "ble_seen": device_id in self.seen,
                    }
                    for device_id, device in self.inventory.items()
                    if device_id in visible_devices
                ],
            },
            retain=True,
        )

    def publish_device_info(self, device_id: str, device: Mapping[str, Any]) -> None:
        self.mqtt_publish(
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
        self.mqtt_publish(f"devices/{device_id}/info", None, retain=True)
        self.mqtt_publish(f"devices/{device_id}/availability", None, retain=True)

    def publish_home_assistant_discovery(self, device_id: str, device: Mapping[str, Any]) -> None:
        for topic, payload in build_discovery_configs(
            self.settings.topic_prefix,
            self.settings.discovery_prefix,
            device_id,
            device,
        ):
            self.mqtt_publish_absolute(topic, payload, retain=True)

    def clear_home_assistant_discovery(self, device_id: str, device: Mapping[str, Any]) -> None:
        for topic in discovery_topics_for_device(self.settings.discovery_prefix, device_id, device):
            self.mqtt_publish_absolute(topic, None, retain=True)

    def on_advertisement(self, device: BLEDevice, advertisement: AdvertisementData) -> None:
        parsed = parse_switchbot_advertisement(device, advertisement)
        if not parsed:
            return
        address = getattr(device, "address", "").replace(":", "").upper()
        device_id = self.resolve_device_id(address, parsed)
        if not device_id or device_id not in self.inventory:
            return
        self.publish_ble_state(device_id, parsed, device)

    def publish_ble_state(self, device_id: str, parsed: Mapping[str, Any], device: BLEDevice | None) -> None:
        is_new_ble_device = device_id not in self.ble_devices
        self.ble_devices.add(device_id)
        self.seen[device_id] = time.monotonic()
        if is_new_ble_device:
            self.publish_inventory()
            self.publish_device_info(device_id, self.inventory[device_id])
            self.publish_home_assistant_discovery(device_id, self.inventory[device_id])
        self.mqtt_publish(f"devices/{device_id}/availability", "online", retain=True)
        self.mqtt_publish(
            f"devices/{device_id}/state",
            {
                "device_id": device_id,
                "observed_at": utc_now(),
                "rssi_dbm": getattr(device, "rssi", None) if device is not None else None,
                "pyswitchbot": parsed,
            },
        )
        log("ble_device_seen", device_id=device_id)

    def resolve_device_id(self, address: str, parsed: Mapping[str, Any]) -> str | None:
        if address in self.inventory:
            return address
        for key in ("address", "device_id", "deviceId", "mac", "mac_address"):
            value = parsed.get(key)
            if isinstance(value, str) and value.replace(":", "").upper() in self.inventory:
                return value.replace(":", "").upper()
        return None

    def mqtt_publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        if self.mqtt is None:
            return
        self.mqtt.publish(topic, payload, retain=retain)

    def mqtt_publish_absolute(self, topic: str, payload: Any, retain: bool = False) -> None:
        if self.mqtt is None:
            return
        self.mqtt.publish_raw(topic, payload, retain=retain)
