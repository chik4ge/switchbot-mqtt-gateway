from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from switchbot_mqtt_gateway.gateway.publisher import GatewayPublisher
from switchbot_mqtt_gateway.gateway.state import GatewayState
from switchbot_mqtt_gateway.switchbot.devices.registry import build_device, profile_for_device
from switchbot_mqtt_gateway.switchbot.dispatcher import execute_command
from switchbot_mqtt_gateway.utils import utc_now


class CommandService:
    def __init__(self, state: GatewayState, publisher: GatewayPublisher) -> None:
        self.state = state
        self.publisher = publisher

    async def handle(self, device_id: str, payload: Mapping[str, Any]) -> None:
        request_id = str(payload.get("request_id") or "")
        if request_id and request_id in self.state.command_results:
            self.publisher.publish(
                f"devices/{device_id}/events/command_result",
                self.state.command_results[request_id],
            )
            return

        result = await self.execute(device_id, payload)
        if request_id:
            self.state.command_results[request_id] = result
        self.publisher.publish(f"devices/{device_id}/events/command_result", result)

    async def execute(self, device_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "request_id": payload.get("request_id"),
            "action": str(payload.get("action") or ""),
            "completed_at": utc_now(),
        }
        if device_id not in self.state.inventory:
            return {**result, "status": "failed", "error": "device_not_found"}
        if device_id not in self.state.ble_addresses:
            return {**result, "status": "failed", "error": "device_not_seen"}

        device_info = self.state.inventory[device_id]
        profile = profile_for_device(device_info)
        if profile is None:
            return {**result, "status": "failed", "error": "unsupported_device_type"}
        try:
            device = build_device(
                profile,
                self.state.ble_addresses[device_id],
                device_info.get("deviceName"),
            )
            ok = await execute_command(profile, device, payload)
        except Exception as exc:
            return {**result, "status": "failed", "error": str(exc)}
        return {**result, "status": "succeeded" if ok is not False else "failed"}

