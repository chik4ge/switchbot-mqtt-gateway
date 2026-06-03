from __future__ import annotations

from switchbot_mqtt_gateway.switchbot.capabilities.sensors import CO2, HUMIDITY, RSSI, TEMPERATURE
from switchbot_mqtt_gateway.switchbot.devices.base import DeviceProfile

METER_PRO_CO2 = DeviceProfile(
    device_types=("MeterPro(CO2)", "Meter Pro CO2"),
    capabilities=(TEMPERATURE, HUMIDITY, CO2, RSSI),
)

