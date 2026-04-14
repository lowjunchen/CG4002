# Capstone Comms

This folder contains the MQTT broker, certificate tooling, client helpers, and visualizer integration for the communications layer.

## Layout

- `docker-compose.yml`: starts Mosquitto and Node-RED locally.
- `mosquitto/`: broker config, certificates, and certificate scripts.
- `ultra96/`: SSH tunnel helpers and reusable MQTT client code for Ultra96 access.
- `visualizer/`: Unity MQTT subscriber script and optional MQTT-to-WebSocket bridge.
- `simulator/`: local MQTT publisher used to simulate device traffic.
- `node-red-data/`: persisted Node-RED flow data.
- `communications_architecture.puml`: high-level architecture diagram.

## Current Working Flows

### 1. Broker on laptop

Start the local broker stack from this folder:

```bash
docker compose up -d
```

This brings up:

- Mosquitto on `8883`
- Node-RED on `1880`

### 2. Hardware devices

The ESP32 headset and gloves connect directly to Mosquitto over mTLS on `8883`.

Relevant topics:

- `sensors/device/1`
- `sensors/device/2`
- `sensors/headset/1`
- `audio/headset/<id>` when audio publishing is enabled

### 3. Ultra96 / FPGA

When the Ultra96 cannot reach the broker directly, use the reverse SSH tunnel in `ultra96/` so the board connects to `localhost:18883` and still uses MQTT over TLS.

See [ultra96/README.md](/Users/yeoyao/Github_NEW/capstone/Comms/ultra96/README.md:1).

### 4. Visualizer

Unity should connect directly to the broker over MQTT/TLS using `MQTTnet`.

If a consumer only speaks WebSocket, use `visualizer/ws_bridge.py` as an adapter.

See [visualizer/README.md](/Users/yeoyao/Github_NEW/capstone/Comms/visualizer/README.md:1).

## Common Tasks

### Start everything locally

```bash
cd Comms
docker compose up -d
```

### Inspect the broker

```bash
docker ps --filter name=mosquitto --filter name=nodered
```

### Verify MQTT traffic over TLS

```bash
docker exec mosquitto sh -c 'mosquitto_sub -h localhost -p 8883 \
  --cafile /mosquitto/config/certs/ca.crt \
  --cert /mosquitto/config/certs/clients/ultra96fpga.crt \
  --key /mosquitto/config/certs/clients/ultra96fpga.key \
  -t "sensors/#"'
```

## Docs

- [mosquitto/CERTS.md](/Users/yeoyao/Github_NEW/capstone/Comms/mosquitto/CERTS.md:1): operational certificate guide
- [mosquitto/MTLS_EXPLAINER.md](/Users/yeoyao/Github_NEW/capstone/Comms/mosquitto/MTLS_EXPLAINER.md:1): short mTLS background
- [ultra96/README.md](/Users/yeoyao/Github_NEW/capstone/Comms/ultra96/README.md:1): Ultra96 tunnel setup
- [visualizer/README.md](/Users/yeoyao/Github_NEW/capstone/Comms/visualizer/README.md:1): Unity and WebSocket visualizer setup
- [communications_architecture.puml](/Users/yeoyao/Github_NEW/capstone/Comms/communications_architecture.puml:1): architecture diagram
