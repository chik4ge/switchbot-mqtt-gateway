from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from switchbot_mqtt_gateway.gateway.inventory import InventoryService
from switchbot_mqtt_gateway.gateway.publisher import GatewayPublisher
from switchbot_mqtt_gateway.gateway.state import GatewayState
from switchbot_mqtt_gateway.switchbot.ble import parse_switchbot_advertisement
from switchbot_mqtt_gateway.switchbot.devices.registry import profile_for_device
from switchbot_mqtt_gateway.switchbot.normalization import build_normalized_state
from switchbot_mqtt_gateway.utils import log, utc_now


class BleService:
    def __init__(
        self,
        state: GatewayState,
        publisher: GatewayPublisher,
        inventory: InventoryService,
    ) -> None:
        self.state = state
        self.publisher = publisher
        self.inventory = inventory

    def on_advertisement(self, device: BLEDevice, advertisement: AdvertisementData) -> None:
        parsed = parse_switchbot_advertisement(device, advertisement)
        if not parsed:
            return
        address = getattr(device, "address", "").replace(":", "").upper()
        device_id = self.resolve_device_id(address, parsed)
        if not device_id or device_id not in self.state.inventory:
            return
        self.publish_state(device_id, parsed, device)

    def publish_state(
        self,
        device_id: str,
        parsed: Mapping[str, Any],
        device: BLEDevice | None,
    ) -> None:
        is_new_ble_device = device_id not in self.state.ble_devices
        self.state.ble_devices.add(device_id)
        address = parsed.get("address")
        if isinstance(address, str):
            self.state.ble_addresses[device_id] = address
        self.state.seen[device_id] = time.monotonic()
        device_info = self.state.inventory[device_id]
        if is_new_ble_device:
            self.inventory.publish_inventory()
            self.publisher.publish_device_info(device_id, device_info)
            self.publisher.publish_home_assistant_discovery(device_id, device_info)
        self.publisher.publish(f"devices/{device_id}/availability", "online", retain=True)
        rssi_dbm = getattr(device, "rssi", None) if device is not None else None
        self.publisher.publish(
            f"devices/{device_id}/state",
            {
                "device_id": device_id,
                "observed_at": utc_now(),
                "rssi_dbm": rssi_dbm,
                "normalized": build_normalized_state(
                    profile_for_device(device_info),
                    parsed,
                    rssi_dbm,
                ),
                "pyswitchbot": parsed,
            },
        )
        log("ble_device_seen", device_id=device_id)

    def resolve_device_id(self, address: str, parsed: Mapping[str, Any]) -> str | None:
        if address in self.state.inventory:
            return address
        for key in ("address", "device_id", "deviceId", "mac", "mac_address"):
            value = parsed.get(key)
            if isinstance(value, str) and value.replace(":", "").upper() in self.state.inventory:
                return value.replace(":", "").upper()
        return None

