from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from switchbot_mqtt_gateway.gateway import Gateway
import switchbot_mqtt_gateway.gateway.commands as gateway_commands
from switchbot_mqtt_gateway.gateway.state import COMMAND_RESULT_CACHE_SIZE
from switchbot_mqtt_gateway.home_assistant import build_discovery_configs
from switchbot_mqtt_gateway.switchbot.capabilities.color_temperature_light import (
    set_color_temperature_light,
)
from switchbot_mqtt_gateway.switchbot.capabilities.dimmable_light import set_light
from switchbot_mqtt_gateway.switchbot.devices.registry import profile_for_device_type
from switchbot_mqtt_gateway.switchbot.normalization import build_normalized_state
from switchbot_mqtt_gateway.switchbot.openapi import SwitchBotOpenApi
from switchbot_mqtt_gateway.switchbot.parsing import parse_bool


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
        {"address": "AA:BB:CC:DD:EE:FF", "data": {"data": {"isOn": True}}},
        device=None,
    )

    assert "AABBCCDDEEFF" in gateway.ble_devices
    assert any(topic == "gateway/inventory" for topic, _, _ in mqtt.published)
    assert any(topic == "devices/AABBCCDDEEFF/info" and retain for topic, _, retain in mqtt.published)
    assert ("devices/AABBCCDDEEFF/availability", "online", True) in mqtt.published
    state_topic, state_payload, retain = mqtt.published[-1]
    assert state_topic == "devices/AABBCCDDEEFF/state"
    assert retain is True
    assert state_payload["device_id"] == "AABBCCDDEEFF"
    assert state_payload["pyswitchbot"]["data"]["data"]["isOn"] is True
    assert state_payload["normalized"]["is_on"] is True
    assert any(
        topic == "homeassistant/light/AABBCCDDEEFF/light/config" and retain
        for topic, _, retain in mqtt.published
    )
    assert any(
        topic == "homeassistant/sensor/AABBCCDDEEFF/rssi/config" and retain
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
                "homeassistant/switch/DEVICE1/power_state/config",
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


def test_build_normalized_state_maps_common_fields() -> None:
    normalized = build_normalized_state(
        profile_for_device_type("Plug Mini (JP)"),
        {
            "rssi": -55,
            "data": {
                "modelFriendlyName": "Plug Mini (JP)",
                "modelName": "WoPlug",
                "data": {
                    "isOn": True,
                    "power": 19.6,
                    "wifi_rssi": -25,
                    "sequence_number": 7,
                },
            },
        }
    )

    assert normalized == {
        "model": "Plug Mini (JP)",
        "model_name": "WoPlug",
        "is_on": True,
        "power_w": 19.6,
        "wifi_rssi_dbm": -25,
        "sequence_number": 7,
        "rssi_dbm": -55,
    }


def test_parse_bool_is_explicit() -> None:
    assert parse_bool("true") is True
    assert parse_bool("false") is False
    assert parse_bool("off") is False
    assert parse_bool("unknown") is None


def test_build_normalized_state_does_not_treat_false_string_as_true() -> None:
    normalized = build_normalized_state(
        profile_for_device_type("Strip Light"),
        {"data": {"data": {"isOn": "false"}}},
    )

    assert normalized["is_on"] is False


def test_handle_command_executes_seen_device_command(monkeypatch: pytest.MonkeyPatch) -> None:
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
    gateway.ble_addresses["AABBCCDDEEFF"] = "AA:BB:CC:DD:EE:FF"

    class FakeDevice:
        pass

    async def fake_execute(_profile: object, device: object, payload: dict[str, Any]) -> bool:
        assert isinstance(device, FakeDevice)
        assert payload["action"] == "set_power"
        return True

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: FakeDevice())
    monkeypatch.setattr(gateway_commands, "execute_command", fake_execute)

    asyncio.run(
        gateway.handle_command(
            "AABBCCDDEEFF",
            {"request_id": "request-1", "action": "set_power", "value": "on"},
        )
    )

    topic, payload, retain = mqtt.published[-1]
    assert topic == "devices/AABBCCDDEEFF/events/command_result"
    assert retain is False
    assert payload["request_id"] == "request-1"
    assert payload["action"] == "set_power"
    assert payload["status"] == "succeeded"


def test_handle_command_republishes_duplicate_request(monkeypatch: pytest.MonkeyPatch) -> None:
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
    gateway.ble_addresses["AABBCCDDEEFF"] = "AA:BB:CC:DD:EE:FF"
    calls = 0

    class FakeDevice:
        pass

    async def fake_execute(_profile: object, _device: object, _payload: dict[str, Any]) -> bool:
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: FakeDevice())
    monkeypatch.setattr(gateway_commands, "execute_command", fake_execute)

    command = {"request_id": "request-1", "action": "set_power", "value": "on"}
    asyncio.run(gateway.handle_command("AABBCCDDEEFF", command))
    asyncio.run(gateway.handle_command("AABBCCDDEEFF", command))

    assert calls == 1
    assert len(
        [
            topic
            for topic, _, _ in mqtt.published
            if topic == "devices/AABBCCDDEEFF/events/command_result"
        ]
    ) == 2


def test_same_request_id_is_executed_for_each_device(monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {
        device_id: {
            "deviceId": device_id,
            "deviceName": device_id,
            "deviceType": "Strip Light",
        }
        for device_id in ("DEVICE1", "DEVICE2")
    }
    gateway, _ = gateway_with_inventory(devices)
    gateway.inventory = devices
    gateway.ble_addresses.update({"DEVICE1": "AA:AA", "DEVICE2": "BB:BB"})
    calls = 0

    async def fake_execute(*_args: object) -> bool:
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: object())
    monkeypatch.setattr(gateway_commands, "execute_command", fake_execute)

    command = {"request_id": "same-id", "action": "turn_on"}
    asyncio.run(gateway.handle_command("DEVICE1", command))
    asyncio.run(gateway.handle_command("DEVICE2", command))

    assert calls == 2
    assert set(gateway.command_results) == {
        ("DEVICE1", "same-id"),
        ("DEVICE2", "same-id"),
    }


def test_concurrent_duplicate_command_is_executed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, mqtt = gateway_with_inventory(
        {
            "DEVICE1": {
                "deviceId": "DEVICE1",
                "deviceName": "Bot",
                "deviceType": "Bot",
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]
    gateway.ble_addresses["DEVICE1"] = "AA:BB"
    calls = 0
    release = asyncio.Event()

    async def fake_execute(*_args: object) -> bool:
        nonlocal calls
        calls += 1
        await release.wait()
        return True

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: object())
    monkeypatch.setattr(gateway_commands, "execute_command", fake_execute)

    async def run_commands() -> None:
        command = {"request_id": "same-id", "action": "press"}
        first = asyncio.create_task(gateway.handle_command("DEVICE1", command))
        await asyncio.sleep(0)
        second = asyncio.create_task(gateway.handle_command("DEVICE1", command))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)

    asyncio.run(run_commands())

    assert calls == 1
    assert len(
        [
            topic
            for topic, _, _ in mqtt.published
            if topic == "devices/DEVICE1/events/command_result"
        ]
    ) == 2


def test_command_result_cache_discards_oldest_entry() -> None:
    gateway, _ = gateway_with_inventory({})

    for index in range(COMMAND_RESULT_CACHE_SIZE + 1):
        asyncio.run(
            gateway.handle_command(
                "DEVICE1",
                {"request_id": f"request-{index}", "action": "turn_on"},
            )
        )

    assert len(gateway.command_results) == COMMAND_RESULT_CACHE_SIZE
    assert ("DEVICE1", "request-0") not in gateway.command_results


def test_light_discovery_uses_template_schema_command() -> None:
    configs = dict(
        build_discovery_configs(
            "switchbot",
            "homeassistant",
            "DEVICE1",
            {"deviceId": "DEVICE1", "deviceName": "Light", "deviceType": "Ceiling Light"},
        )
    )
    payload = configs["homeassistant/light/DEVICE1/light/config"]

    assert payload["schema"] == "template"
    assert payload["command_topic"] == "switchbot/devices/DEVICE1/commands"
    assert "brightness_command_topic" not in payload
    assert "brightness_command_template" not in payload
    assert "* 255 / 100" in payload["brightness_template"]
    assert '"action":"set_color_temperature_light"' in payload["command_on_template"]
    assert payload["color_temp_kelvin"] is True
    assert payload["min_kelvin"] == 2700
    assert payload["max_kelvin"] == 6500
    assert "color_temp_kelvin_command_topic" not in payload


def test_set_light_converts_home_assistant_brightness_to_percent() -> None:
    class FakeLight:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int | None]] = []

        async def turn_on(self) -> bool:
            self.calls.append(("turn_on", None))
            return True

        async def set_brightness(self, value: int) -> bool:
            self.calls.append(("set_brightness", value))
            return True

    light = FakeLight()
    asyncio.run(set_light(light, {"state": "on", "brightness": 255}))

    assert light.calls == [("turn_on", None), ("set_brightness", 100)]


def test_set_color_temperature_light_converts_brightness() -> None:
    class FakeLight:
        def __init__(self) -> None:
            self.values: tuple[int, int] | None = None

        async def set_color_temp(self, brightness: int, temperature: int) -> bool:
            self.values = (brightness, temperature)
            return True

    light = FakeLight()
    asyncio.run(
        set_color_temperature_light(
            light,
            {"state": "on", "brightness": 128, "color_temperature_kelvin": 4000},
        )
    )

    assert light.values == (50, 4000)


def test_color_temperature_command_uses_last_brightness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _ = gateway_with_inventory(
        {
            "DEVICE1": {
                "deviceId": "DEVICE1",
                "deviceName": "Ceiling light",
                "deviceType": "Ceiling Light",
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]
    gateway.ble_addresses["DEVICE1"] = "AA:BB"
    gateway.state.normalized_states["DEVICE1"] = {"brightness_percent": 37}
    received: dict[str, Any] = {}

    async def fake_execute(_profile: object, _device: object, payload: dict[str, Any]) -> bool:
        received.update(payload)
        return True

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: object())
    monkeypatch.setattr(gateway_commands, "execute_command", fake_execute)

    asyncio.run(
        gateway.handle_command(
            "DEVICE1",
            {
                "request_id": "color-1",
                "action": "set_color_temperature_light",
                "color_temperature_kelvin": 4000,
            },
        )
    )

    assert received["brightness_percent"] == 37


def test_resync_mqtt_state_republishes_retained_data() -> None:
    gateway, mqtt = gateway_with_inventory(
        {
            "DEVICE1": {
                "deviceId": "DEVICE1",
                "deviceName": "Light",
                "deviceType": "Strip Light",
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]
    gateway.ble_devices.add("DEVICE1")
    gateway.seen["DEVICE1"] = 1.0
    gateway.state.latest_states["DEVICE1"] = {"device_id": "DEVICE1"}

    asyncio.run(gateway.resync_mqtt_state())

    assert any(topic == "gateway/status" and retain for topic, _, retain in mqtt.published)
    assert any(topic == "gateway/inventory" and retain for topic, _, retain in mqtt.published)
    assert ("devices/DEVICE1/state", {"device_id": "DEVICE1"}, True) in mqtt.published
    assert any(topic.startswith("homeassistant/") and retain for topic, _, retain in mqtt.published)


def test_reload_failure_publishes_failed_result() -> None:
    class FailingApi:
        async def fetch_devices(self) -> dict[str, dict[str, Any]]:
            raise RuntimeError("secret upstream detail")

    gateway, mqtt = gateway_with_inventory({})
    gateway.inventory_service.api = FailingApi()

    asyncio.run(gateway.reload({"request_id": "reload-1"}))

    topic, payload, retain = mqtt.published[-1]
    assert topic == "gateway/events/reload_result"
    assert retain is False
    assert payload == {
        "request_id": "reload-1",
        "status": "failed",
        "error": "inventory refresh failed",
        "completed_at": payload["completed_at"],
    }


def test_refresh_inventory_prunes_removed_device_state() -> None:
    gateway, _ = gateway_with_inventory({})
    gateway.inventory = {"REMOVED": {"deviceId": "REMOVED", "deviceType": "Meter"}}
    gateway.ble_devices.add("REMOVED")
    gateway.ble_addresses["REMOVED"] = "AA:BB"
    gateway.seen["REMOVED"] = 1.0

    asyncio.run(gateway.refresh_inventory())

    assert "REMOVED" not in gateway.ble_devices
    assert "REMOVED" not in gateway.ble_addresses
    assert "REMOVED" not in gateway.seen


def test_switchbot_api_rejects_application_error() -> None:
    with pytest.raises(RuntimeError, match="statusCode=190"):
        SwitchBotOpenApi._devices_from_payload(
            {
                "statusCode": 190,
                "body": {},
                "message": "Requests reached the daily limit",
            }
        )


def test_switchbot_api_parses_successful_device_response() -> None:
    devices = SwitchBotOpenApi._devices_from_payload(
        {
            "statusCode": 100,
            "body": {
                "deviceList": [{"deviceId": "aabb", "deviceType": "Meter"}],
                "infraredRemoteList": [{"deviceId": "ccdd", "deviceType": "TV"}],
            },
        }
    )

    assert set(devices) == {"AABB", "CCDD"}


def test_failed_retained_delete_is_retried_after_reconnect() -> None:
    class PublishResult:
        def __init__(self, rc: int) -> None:
            self.rc = rc

    class DisconnectingMqtt(RecordingMqtt):
        def __init__(self) -> None:
            super().__init__()
            self.connected = False

        def publish(self, topic: str, payload: Any, retain: bool = False) -> PublishResult:
            super().publish(topic, payload, retain)
            return PublishResult(0 if self.connected else 4)

        def publish_raw(self, topic: str, payload: Any, retain: bool = False) -> PublishResult:
            super().publish_raw(topic, payload, retain)
            return PublishResult(0 if self.connected else 4)

    gateway, _ = gateway_with_inventory({})
    mqtt = DisconnectingMqtt()
    gateway.mqtt = mqtt  # type: ignore[assignment]
    removed = {
        "deviceId": "REMOVED",
        "deviceName": "Removed",
        "deviceType": "Strip Light",
    }
    gateway.inventory = {"REMOVED": removed}
    gateway.ble_devices.add("REMOVED")

    asyncio.run(gateway.refresh_inventory())

    assert gateway.state.pending_retained_deletes == {"REMOVED": removed}

    mqtt.connected = True
    asyncio.run(gateway.resync_mqtt_state())

    assert gateway.state.pending_retained_deletes == {}


def test_gateway_started_at_is_stable_across_republish() -> None:
    gateway, mqtt = gateway_with_inventory({})

    gateway.publish_gateway_status()
    gateway.publish_gateway_status()

    statuses = [
        payload
        for topic, payload, _ in mqtt.published
        if topic == "gateway/status"
    ]
    assert statuses[0]["started_at"] == statuses[1]["started_at"]


def test_command_fails_for_unseen_device() -> None:
    gateway, _ = gateway_with_inventory(
        {
            "AABBCCDDEEFF": {
                "deviceId": "AABBCCDDEEFF",
                "deviceName": "Light strip",
                "deviceType": "Strip Light",
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]

    result = asyncio.run(
        gateway.execute_device_command("AABBCCDDEEFF", {"request_id": "r1", "action": "turn_on"})
    )

    assert result["status"] == "failed"
    assert result["error"] == "device_not_seen"


def test_command_fails_for_unsupported_action(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway, _ = gateway_with_inventory(
        {
            "AABBCCDDEEFF": {
                "deviceId": "AABBCCDDEEFF",
                "deviceName": "Light strip",
                "deviceType": "Strip Light",
            }
        }
    )
    gateway.inventory = gateway.api.devices  # type: ignore[attr-defined]
    gateway.ble_addresses["AABBCCDDEEFF"] = "AA:BB:CC:DD:EE:FF"

    class FakeDevice:
        pass

    monkeypatch.setattr(gateway_commands, "build_device", lambda *_args: FakeDevice())

    result = asyncio.run(gateway.execute_device_command("AABBCCDDEEFF", {"action": "press"}))

    assert result["status"] == "failed"
    assert result["error"] == "unsupported_action"
