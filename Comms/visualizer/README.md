# Visualizer Integration

This folder supports two visualizer paths:

1. Unity connects directly to Mosquitto over MQTT/TLS.
2. `ws_bridge.py` adapts MQTT topics to WebSocket for clients that do not speak MQTT.

## Recommended Path: Unity Direct to MQTT

The current Unity integration uses `MQTTnet` and [UnityMqttNetSub.cs](/Users/yeoyao/Github_NEW/capstone/Comms/visualizer/UnityMqttNetSub.cs:1).

### Generate the Unity client certificate

From `Comms/mosquitto`:

```bash
PFX_PASS=capstone PFX_LEGACY=1 ./gen_client_cert.sh unity_pub
```

This produces:

- `Comms/mosquitto/certs/clients/unity_pub.crt`
- `Comms/mosquitto/certs/clients/unity_pub.key`
- `Comms/mosquitto/certs/clients/unity_pub.pfx`

Unity uses:

- `ca.crt` to trust the broker
- `unity_pub.pfx` to authenticate to the broker

### Add MQTTnet to Unity

Download `MQTTnet.4.3.7.1207.nupkg`, extract `lib/netstandard2.0/MQTTnet.dll`, and place it in:

```text
Assets/Plugins/MQTTnet.dll
```

On macOS, remove quarantine if Unity refuses to load it:

```bash
xattr -dr com.apple.quarantine Assets/Plugins/MQTTnet.dll
```

### Add TLS files to Unity

Place these files in the Unity project:

```text
Assets/StreamingAssets/ca.crt
Assets/StreamingAssets/unity_pub.pfx
```

### Add and configure the subscriber

Copy:

- `Comms/visualizer/UnityMqttNetSub.cs`

Suggested Unity setup:

- API Compatibility Level: `.NET Standard 2.1`
- GameObject: `MQTTClient`
- Component: `UnityMqttNetSub`

Inspector values:

- `host`: broker hostname or laptop IP
- `port`: `8883`
- `topic1`: `sensors/device/1`
- `topic2`: `sensors/device/2`
- `caFile`: `ca.crt`
- `pfxFile`: `unity_pub.pfx`
- `pfxPassword`: `capstone`

### Verify the feed

Start the broker:

```bash
cd Comms
docker compose up -d
```

Generate traffic with the simulator:

```bash
python3 Comms/simulator/mqtt_simulator.py --tls --host <BROKER_HOST> --port 8883
```

Expected Unity logs:

- `MQTT CONNECT OK`
- `Subscribed: sensors/device/1, sensors/device/2`

## Optional Path: MQTT to WebSocket Bridge

Use [ws_bridge.py](/Users/yeoyao/Github_NEW/capstone/Comms/visualizer/ws_bridge.py:1) only when the visualizer cannot speak MQTT directly.

Install dependencies:

```bash
python3 -m pip install -r Comms/visualizer/requirements.txt
```

TLS MQTT example:

```bash
python3 Comms/visualizer/ws_bridge.py \
  --mqtt-host 127.0.0.1 --mqtt-port 8883 \
  --mqtt-topic "sensors/#" \
  --mqtt-tls \
  --ca Comms/mosquitto/certs/ca.crt \
  --cert Comms/mosquitto/certs/clients/laptop_pub.crt \
  --key Comms/mosquitto/certs/clients/laptop_pub.key \
  --ws-host 0.0.0.0 --ws-port 8765
```

Each MQTT message is forwarded as JSON:

```json
{"topic":"sensors/device/2","payload":"{...}","ts":1710000000.123}
```

To send WebSocket traffic back into MQTT, add:

```bash
--ws-to-mqtt-topic "visualizer/in"
```

## Troubleshooting

- MQTTnet namespace errors: use the DLL from `lib/netstandard2.0`.
- TLS failures: verify the broker host matches the server certificate SAN.
- Missing Unity auth files: regenerate `unity_pub` with `gen_client_cert.sh`.
- Full CA regeneration: hardware devices must be reflashed after `Hardware/certs.h` is regenerated.
