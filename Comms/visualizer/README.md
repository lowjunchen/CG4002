# Visualizer WebSocket Bridge (Preliminary)

This folder provides a minimal MQTT → WebSocket bridge for the Visualizer.

## 1) Install deps (Ultra96 or laptop)

```bash
python3 -m pip install -r Comms/visualizer/requirements.txt
```

## 2) Run the bridge

Plain MQTT (1883):
```bash
python3 Comms/visualizer/ws_bridge.py \
  --mqtt-host 127.0.0.1 --mqtt-port 1883 \
  --mqtt-topic "sensors/#" \
  --ws-host 0.0.0.0 --ws-port 8765
```

TLS MQTT (8883) example:
```bash
python3 Comms/visualizer/ws_bridge.py \
  --mqtt-host 127.0.0.1 --mqtt-port 8883 \
  --mqtt-topic "sensors/#" \
  --mqtt-tls \
  --ca Comms/mosquitto/certs/ca.crt \
  --cert Comms/mosquitto/certs/clients/simulator.crt \
  --key Comms/mosquitto/certs/clients/simulator.key \
  --ws-host 0.0.0.0 --ws-port 8765
```

## 3) WebSocket message format

Each MQTT message is forwarded as JSON:

```json
{"topic":"sensors/device/2","payload":"{...}","ts":1710000000.123}
```

## 4) Optional: WebSocket → MQTT

If you want the Visualizer to send commands back, add:

```bash
--ws-to-mqtt-topic "visualizer/in"
```

Then any text message received over WebSocket is published to that topic.
