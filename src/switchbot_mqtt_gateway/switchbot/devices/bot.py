from __future__ import annotations

from switchbot.devices.bot import Switchbot

from switchbot_mqtt_gateway.switchbot.capabilities.button_press import BUTTON_PRESS
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

BOT = DeviceProfile(device_types=("Bot",), capabilities=(BUTTON_PRESS,), device_class=Switchbot)

