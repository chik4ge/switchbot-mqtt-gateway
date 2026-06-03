# switchbot-mqtt-gateway

SwitchBot BLE advertisements are forwarded to MQTT. The gateway fetches the owned device inventory from SwitchBot Open API and only publishes BLE data for devices present in that inventory.

## Run

```sh
uv sync
uv run switchbot-mqtt-gateway
```

Required environment variables:

```text
SWITCHBOT_API_TOKEN
SWITCHBOT_API_SECRET
MQTT_HOST
MQTT_PORT
MQTT_USERNAME
MQTT_PASSWORD
```

Optional environment variables:

```text
MQTT_TLS_ENABLED=false
MQTT_CA_CERT_PATH=
MQTT_CLIENT_ID=switchbot-mqtt-gateway
MQTT_KEEPALIVE_SECONDS=60
MQTT_TOPIC_PREFIX=switchbot
HOME_ASSISTANT_DISCOVERY_PREFIX=homeassistant
SWITCHBOT_INVENTORY_REFRESH_INTERVAL_SECONDS=3600
DEVICE_OFFLINE_AFTER_SECONDS=300
LOG_LEVEL=info
```

## Container

```sh
docker build -t switchbot-mqtt-gateway .
docker run --rm --net=host \
  -v /var/run/dbus:/var/run/dbus \
  --cap-add=NET_ADMIN --cap-add=NET_RAW \
  --env-file .env \
  switchbot-mqtt-gateway
```

The container is an MQTT client. It does not include an MQTT broker.

## Local Compose

```sh
fnox export -f env -o .env
docker compose up --build
```

Open the MQTT debug UI:

```text
http://localhost:8080
```

It connects to `ws://localhost:9001` and subscribes to `switchbot/#` by default.

MQTT messages can be tailed with:

```sh
docker compose --profile debug up mqtt-debug-cli
```

The Compose setup starts a local Mosquitto broker on `127.0.0.1:1883` and a WebSocket listener on `127.0.0.1:9001`.
