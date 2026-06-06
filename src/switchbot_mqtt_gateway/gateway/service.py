from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from switchbot_mqtt_gateway.gateway.ble import BleService
from switchbot_mqtt_gateway.gateway.commands import CommandService
from switchbot_mqtt_gateway.gateway.inventory import InventoryService
from switchbot_mqtt_gateway.gateway.publisher import GatewayPublisher
from switchbot_mqtt_gateway.gateway.state import GatewayState
from switchbot_mqtt_gateway.mqtt.client import MqttClient
from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.switchbot.openapi import SwitchBotOpenApi
from switchbot_mqtt_gateway.utils import log


class Gateway:
    def __init__(self, settings: Settings, api: SwitchBotOpenApi | None = None) -> None:
        self.settings = settings
        self.api = api or SwitchBotOpenApi(settings)
        self.state = GatewayState()
        self.publisher = GatewayPublisher(settings)
        self.inventory_service = InventoryService(self.api, self.state, self.publisher)
        self.command_service = CommandService(self.state, self.publisher)
        self.ble_service = BleService(self.state, self.publisher, self.inventory_service)

    @property
    def mqtt(self) -> MqttClient | None:
        return self.publisher.mqtt

    @mqtt.setter
    def mqtt(self, value: MqttClient | None) -> None:
        self.publisher.mqtt = value

    @property
    def inventory(self) -> dict[str, dict[str, Any]]:
        return self.state.inventory

    @inventory.setter
    def inventory(self, value: dict[str, dict[str, Any]]) -> None:
        self.state.inventory = value

    @property
    def seen(self) -> dict[str, float]:
        return self.state.seen

    @property
    def ble_addresses(self) -> dict[str, str]:
        return self.state.ble_addresses

    @property
    def ble_devices(self) -> set[str]:
        return self.state.ble_devices

    @property
    def command_results(self) -> dict[str, dict[str, Any]]:
        return self.state.command_results

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.mqtt = MqttClient(self.settings, loop, self.reload, self.handle_command)
        self.mqtt.connect()
        self.publisher.publish_gateway_status()
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
        await self.inventory_service.reload(payload)

    async def handle_command(self, device_id: str, payload: Mapping[str, Any]) -> None:
        await self.command_service.handle(device_id, payload)

    async def execute_device_command(
        self, device_id: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await self.command_service.execute(device_id, payload)

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
                    self.publisher.publish(
                        f"devices/{device_id}/availability",
                        "offline",
                        retain=True,
                    )

    async def refresh_inventory(self) -> None:
        await self.inventory_service.refresh()

    def publish_inventory(self) -> None:
        self.inventory_service.publish_inventory()

    def publish_gateway_status(self) -> None:
        self.publisher.publish_gateway_status()

    def publish_device_info(self, device_id: str, device: Mapping[str, Any]) -> None:
        self.publisher.publish_device_info(device_id, device)

    def clear_retained_device_topics(self, device_id: str) -> None:
        self.publisher.clear_retained_device_topics(device_id)

    def publish_home_assistant_discovery(
        self, device_id: str, device: Mapping[str, Any]
    ) -> None:
        self.publisher.publish_home_assistant_discovery(device_id, device)

    def clear_home_assistant_discovery(
        self, device_id: str, device: Mapping[str, Any]
    ) -> None:
        self.publisher.clear_home_assistant_discovery(device_id, device)

    def on_advertisement(self, device: BLEDevice, advertisement: AdvertisementData) -> None:
        self.ble_service.on_advertisement(device, advertisement)

    def publish_ble_state(
        self,
        device_id: str,
        parsed: Mapping[str, Any],
        device: BLEDevice | None,
    ) -> None:
        self.ble_service.publish_state(device_id, parsed, device)

    def resolve_device_id(self, address: str, parsed: Mapping[str, Any]) -> str | None:
        return self.ble_service.resolve_device_id(address, parsed)

    def mqtt_publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        self.publisher.publish(topic, payload, retain)

    def mqtt_publish_absolute(self, topic: str, payload: Any, retain: bool = False) -> None:
        self.publisher.publish_absolute(topic, payload, retain)
