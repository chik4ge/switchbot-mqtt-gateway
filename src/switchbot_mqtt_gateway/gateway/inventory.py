from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

from switchbot_mqtt_gateway.gateway.publisher import GatewayPublisher
from switchbot_mqtt_gateway.gateway.state import GatewayState
from switchbot_mqtt_gateway.utils import log, utc_now


class DeviceInventoryApi(Protocol):
    async def fetch_devices(self) -> dict[str, dict[str, Any]]: ...


class InventoryService:
    def __init__(
        self,
        api: DeviceInventoryApi,
        state: GatewayState,
        publisher: GatewayPublisher,
    ) -> None:
        self.api = api
        self.state = state
        self.publisher = publisher

    async def reload(self, payload: Mapping[str, Any]) -> None:
        before = dict(self.state.inventory)
        try:
            await self.refresh()
        except Exception as exc:
            log("inventory_reload_failed", logging.ERROR, error=str(exc))
            self.publisher.publish(
                "gateway/events/reload_result",
                {
                    "request_id": payload.get("request_id"),
                    "status": "failed",
                    "error": "inventory refresh failed",
                    "completed_at": utc_now(),
                },
            )
            return
        added = self.state.inventory.keys() - before.keys()
        removed = before.keys() - self.state.inventory.keys()
        updated = {
            device_id
            for device_id in self.state.inventory.keys() & before.keys()
            if self.state.inventory[device_id] != before[device_id]
        }
        self.publisher.publish(
            "gateway/events/reload_result",
            {
                "request_id": payload.get("request_id"),
                "status": "succeeded",
                "devices_total": len(self.state.inventory),
                "devices_added": len(added),
                "devices_updated": len(updated),
                "devices_removed": len(removed),
                "completed_at": utc_now(),
            },
        )

    async def refresh(self) -> None:
        devices = await self.api.fetch_devices()
        before = self.state.inventory
        removed = before.keys() - devices.keys()
        removed_ble_devices = removed & self.state.ble_devices
        self.state.inventory = devices
        for device_id, device in devices.items():
            if device_id in self.state.ble_devices:
                self.publisher.publish_device_info(device_id, device)
                self.publisher.publish_home_assistant_discovery(device_id, device)
            else:
                self.publisher.clear_retained_device_topics(device_id)
                self.publisher.clear_home_assistant_discovery(device_id, device)
        for device_id in removed_ble_devices:
            self.publisher.publish(f"devices/{device_id}/availability", "offline", retain=True)
            device = before[device_id]
            retained_cleared = self.publisher.clear_retained_device_topics(device_id)
            discovery_cleared = self.publisher.clear_home_assistant_discovery(device_id, device)
            if not retained_cleared or not discovery_cleared:
                self.state.pending_retained_deletes[device_id] = device
        for device_id in removed:
            self.state.ble_devices.discard(device_id)
            self.state.ble_addresses.pop(device_id, None)
            self.state.seen.pop(device_id, None)
            self.state.normalized_states.pop(device_id, None)
            self.state.latest_states.pop(device_id, None)
        self.publish_inventory()
        log("inventory_refreshed", devices_total=len(devices), devices_removed=len(removed))

    def retry_pending_retained_deletes(self) -> None:
        for device_id, device in list(self.state.pending_retained_deletes.items()):
            retained_cleared = self.publisher.clear_retained_device_topics(device_id)
            discovery_cleared = self.publisher.clear_home_assistant_discovery(device_id, device)
            if retained_cleared and discovery_cleared:
                self.state.pending_retained_deletes.pop(device_id, None)

    def publish_inventory(self) -> None:
        visible_devices = self.state.ble_devices & self.state.inventory.keys()
        self.publisher.publish(
            "gateway/inventory",
            {
                "refreshed_at": utc_now(),
                "devices_total": len(self.state.inventory),
                "ble_devices_total": len(self.state.ble_devices),
                "published_devices_total": len(visible_devices),
                "devices": [
                    {
                        "device_id": device_id,
                        "name": device.get("deviceName"),
                        "type": device.get("deviceType"),
                        "ble_seen": device_id in self.state.seen,
                    }
                    for device_id, device in self.state.inventory.items()
                    if device_id in visible_devices
                ],
            },
            retain=True,
        )
