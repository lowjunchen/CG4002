# Visualizer WebSocket Bridge (Preliminary)

This folder provides a minimal MQTT → WebSocket bridge for the Visualizer.

## Unity MQTT Setup

The current Unity integration uses `MQTTnet` and connects directly to the broker over TLS.

### 1) Generate the Unity client certificate

From the repo root:

```bash
cd Comms/mosquitto
PFX_PASS=capstone PFX_LEGACY=1 ./gen_client_cert.sh unity_pub
```

This generates:

- `Comms/mosquitto/certs/clients/unity_pub.crt`
- `Comms/mosquitto/certs/clients/unity_pub.key`
- `Comms/mosquitto/certs/clients/unity_pub.pfx`

Unity uses:

- `ca.crt` to verify the broker
- `unity_pub.pfx` to authenticate itself to the broker

### 2) Add MQTTnet to Unity

Download `MQTTnet 4.3.7.1207` from NuGet and extract:

- package: `MQTTnet.4.3.7.1207.nupkg`
- required DLL: `lib/netstandard2.0/MQTTnet.dll`

Place the DLL in the Unity project:

```text
Assets/Plugins/MQTTnet.dll
```

On macOS, if Unity fails to load the DLL, remove quarantine:

```bash
xattr -dr com.apple.quarantine Assets/Plugins/MQTTnet.dll
```

### 3) Add TLS files to Unity

Place these files in the Unity project:

```text
Assets/StreamingAssets/ca.crt
Assets/StreamingAssets/unity_pub.pfx
```

### 4) Add the Unity subscriber script

Use:

- `Comms/visualizer/UnityMqttNetSub.cs`

Place it in the Unity project, for example:

```text
Assets/UnityMqttNetSub.cs
```

### 5) Configure Unity

- Set API Compatibility Level to `.NET Standard 2.1`
- Create an empty GameObject such as `MQTTClient`
- Add the `UnityMqttNetSub` component

Set the following fields in the Inspector:

- `host`: broker IP or laptop IP
- `port`: `8883`
- `topic1`: `sensors/device/1`
- `topic2`: `sensors/device/2`
- `caFile`: `ca.crt`
- `pfxFile`: `unity_pub.pfx`
- `pfxPassword`: `capstone`

### 6) Start the broker

From the repo root:

```bash
cd Comms
docker compose up -d
```

### 7) Test with simulator or hardware

Example simulator command:

```bash
python3 Comms/simulator/mqtt_simulator.py --tls --host <BROKER_HOST> --port 8883
```

Replace `<BROKER_HOST>` with the same host that Unity uses.

### 8) Expected Unity logs

When Unity connects successfully, the Console should show:

- `MQTT CONNECT OK`
- `Subscribed: sensors/device/1, sensors/device/2`

Incoming payloads are then logged as JSON strings from the subscribed topics.

### 9) Troubleshooting

- If Unity shows MQTTnet namespace errors, ensure the DLL is from `lib/netstandard2.0`
- If TLS fails, verify `ca.crt` and `unity_pub.pfx` are present in `Assets/StreamingAssets`
- If broker connection fails, confirm the broker certificate SAN matches the host or IP used by Unity
- If you regenerate all certs, hardware devices must be reflashed with updated `certs.h`

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
