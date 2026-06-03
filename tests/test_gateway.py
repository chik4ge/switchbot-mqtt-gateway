from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from switchbot_mqtt_gateway.gateway import Gateway


class FakeApi:
    def __init__(self, devices: dict[str, dict[str, Any]]) -> None:
        self.devices = devices

    async def fetch_devices(self) -> dict[str, dict[str, Any]]:
        return self.devices


class RecordingMqtt:
    def __init__(self) -> None:
        self.published: list[tuple[str, Any, bool]] = []

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        self.published.append((topic, payload, retain))

    def publish_raw(self, topic: str, payload: Any, retain: bool = False) -> None:
        self.published.append((topic, payload, retain))


def gateway_with_inventory(devices: dict[str, dict[str, Any]]) -> tuple[Gateway, RecordingMqtt]:
    settings = SimpleNamespace(
        device_offline_after_seconds=300,
        discovery_prefix="homeassistant",
        inventory_refresh_seconds=3600,
        topic_prefix="switchbot",
    )
    gateway = Gateway(settings, api=FakeApi(devices))  # type: ignore[arg-type]
    mqtt = RecordingMqtt()
    gateway.mqtt = mqtt  # type: ignore[assignment]
    return gateway, mqtt


def test_refresh_inventory_only_publishes_ble_seen_devices() -> None:
    gateway, mqtt = gateway_with_inventory(
        {
            "BLEDEVICE": {
                "deviceId": "BLEDEVICE",
                "deviceName": "BLE device",
                "deviceType": "Meter",
                "enableCloudService": True,
            },
            "APIONLY": {
                "deviceId": "APIONLY",
                "deviceName": "API only",
                "deviceType": "Remote",
                "enableCloudService": True,
            },
        }
    )
    gateway.ble_devices.add("BLEDEVICE")

    asyncio.run(gateway.refresh_inventory())

    inventory_payload = next(payload for topic, payload, _ in mqtt.published if topic == "gateway/inventory")
    assert inventory_payload["devices_total"] == 2
    assert inventory_payload["ble_devices_total"] == 1
    assert inventory_payload["published_devices_total"] == 1
    assert [device["device_id"] for device in inventory_payload["devices"]] == ["BLEDEVICE"]

    assert any(topic == "devices/BLEDEVICE/info" and retain for topic, _, retain in mqtt.published)
    assert ("devices/APIONLY/info", None, True) in mqtt.published
    assert ("devices/APIONLY/availability", None, True) in mqtt.published


def test_publish_ble_state_adds_device_and_publishes_state() -> None:
    gateway, mqtt = gateway_with_inventory(
        {
            "AABBCCDDEEFF": {
                "deviceId": "AABBCCDDEEFF",
                "deviceName": "Light strip",
                "deviceType": "Strip Light",
                "enableCloudService": True,
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]

    gateway.publish_ble_state(
        "AABBCCDDEEFF",
        {"address": "AA:BB:CC:DD:EE:FF", "data": {"isOn": True}},
        device=None,
    )

    assert "AABBCCDDEEFF" in gateway.ble_devices
    assert any(topic == "gateway/inventory" for topic, _, _ in mqtt.published)
    assert any(topic == "devices/AABBCCDDEEFF/info" and retain for topic, _, retain in mqtt.published)
    assert ("devices/AABBCCDDEEFF/availability", "online", True) in mqtt.published
    state_topic, state_payload, retain = mqtt.published[-1]
    assert state_topic == "devices/AABBCCDDEEFF/state"
    assert retain is False
    assert state_payload["device_id"] == "AABBCCDDEEFF"
    assert state_payload["pyswitchbot"]["data"]["isOn"] is True
    assert any(
        topic == "homeassistant/binary_sensor/AABBCCDDEEFF/power_state/config" and retain
        for topic, _, retain in mqtt.published
    )
    assert any(
        topic == "homeassistant/sensor/AABBCCDDEEFF/brightness/config" and retain
        for topic, _, retain in mqtt.published
    )


def test_resolve_device_id_from_address_or_parsed_alias() -> None:
    gateway, _ = gateway_with_inventory({"AABBCCDDEEFF": {"deviceId": "AABBCCDDEEFF"}})
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]

    assert gateway.resolve_device_id("AABBCCDDEEFF", {}) == "AABBCCDDEEFF"
    assert gateway.resolve_device_id("", {"address": "AA:BB:CC:DD:EE:FF"}) == "AABBCCDDEEFF"
    assert gateway.resolve_device_id("112233445566", {"address": "11:22:33:44:55:66"}) is None


@pytest.mark.parametrize(
    ("device_type", "expected_topics"),
    [
        (
            "MeterPro(CO2)",
            [
                "homeassistant/sensor/DEVICE1/temperature/config",
                "homeassistant/sensor/DEVICE1/humidity/config",
                "homeassistant/sensor/DEVICE1/co2/config",
                "homeassistant/sensor/DEVICE1/rssi/config",
            ],
        ),
        (
            "Plug Mini (JP)",
            [
                "homeassistant/binary_sensor/DEVICE1/power_state/config",
                "homeassistant/sensor/DEVICE1/power/config",
                "homeassistant/sensor/DEVICE1/wifi_rssi/config",
                "homeassistant/sensor/DEVICE1/rssi/config",
            ],
        ),
    ],
)
def test_home_assistant_discovery_configs_are_published(
    device_type: str, expected_topics: list[str]
) -> None:
    gateway, mqtt = gateway_with_inventory(
        {
            "DEVICE1": {
                "deviceId": "DEVICE1",
                "deviceName": "Device 1",
                "deviceType": device_type,
                "enableCloudService": True,
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]

    gateway.publish_ble_state("DEVICE1", {"address": "DE:VI:CE:00:00:01"}, device=None)

    retained_discovery_topics = {
        topic for topic, payload, retain in mqtt.published if topic.startswith("homeassistant/") and retain and payload
    }
    assert retained_discovery_topics == set(expected_topics)
