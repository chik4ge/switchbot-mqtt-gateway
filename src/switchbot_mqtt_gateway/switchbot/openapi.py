from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from typing import Any

import aiohttp

from switchbot_mqtt_gateway.settings import Settings

SWITCHBOT_API_BASE_URL = "https://api.switch-bot.com/v1.1"


class SwitchBotOpenApi:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_devices(self) -> dict[str, dict[str, Any]]:
        nonce = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))
        message = f"{self.settings.switchbot_api_token}{timestamp}{nonce}".encode()
        secret = self.settings.switchbot_api_secret.encode()
        sign = base64.b64encode(hmac.new(secret, message, hashlib.sha256).digest()).decode()
        headers = {
            "Authorization": self.settings.switchbot_api_token,
            "sign": sign,
            "nonce": nonce,
            "t": timestamp,
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{SWITCHBOT_API_BASE_URL}/devices", timeout=30) as response:
                response.raise_for_status()
                payload = await response.json()
        body = payload.get("body") or {}
        devices = [*body.get("deviceList", []), *body.get("infraredRemoteList", [])]
        return {device["deviceId"].upper(): device for device in devices if device.get("deviceId")}

