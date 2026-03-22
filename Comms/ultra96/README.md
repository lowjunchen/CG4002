**Ultra96 SSH Tunnel for MQTT**
Use this when the Ultra96 cannot reach the broker directly due to network restrictions. The tunnel runs over SSH, which is typically allowed even when MQTT is blocked.

This folder provides a simple script with two modes:
- `forward` (recommended): Ultra96 publishes to a remote broker via a local port.
- `reverse`: expose a broker running on Ultra96 to a remote host.

**Files**
- `Comms/ultra96/ssh_tunnel.sh`: starts the tunnel (uses `autossh` if available).
- `Comms/ultra96/tunnel.env.example`: config template.

**1. Create your env file on Ultra96**
```bash
cp Comms/ultra96/tunnel.env.example Comms/ultra96/tunnel.env
```
Edit `Comms/ultra96/tunnel.env` and set:
- `TUNNEL_USER`, `TUNNEL_HOST`
- `BROKER_HOST`, `BROKER_PORT` (for forward mode)
- `LOCAL_PORT` and `REMOTE_PORT` as needed

**2. Forward mode (Ultra96 -> remote broker)**
Use this if the broker is outside the school network.

```bash
MODE=forward Comms/ultra96/ssh_tunnel.sh
```

Then point your Ultra96 MQTT client to:
- host: `localhost`
- port: `LOCAL_PORT` (default `18883`)

**TLS note:** if you are using TLS with a broker certificate that includes `localhost`, this works as-is. If the broker cert does not include `localhost`, you must either:
- issue a cert with `localhost` in SAN, or
- disable hostname verification on the MQTT client.

**3. Reverse mode (expose Ultra96 broker)**
Use this if a broker is running on the Ultra96 and you want to connect from outside.

```bash
MODE=reverse Comms/ultra96/ssh_tunnel.sh
```

By default the remote port binds to `127.0.0.1` for safety. If you want the port accessible externally on the jump host, set:
```
REMOTE_BIND_ADDR=0.0.0.0
```
and ensure the SSH server allows it (`GatewayPorts clientspecified` in `sshd_config`).

**4. Keep the tunnel alive**
Install `autossh` on Ultra96 if available:
```bash
sudo apt-get install -y autossh
```
The script will use it automatically.

**5. Install Python dependency on Ultra96**
```bash
python3 -m pip install -r Comms/ultra96/requirements.txt
```

**6. Python MQTT client on Ultra96**
For a direct or tunnelled mTLS MQTT client on the Ultra96, use:
- `Comms/ultra96/mqtt_client.py`: reusable mTLS client wrapper
- `Comms/ultra96/run_dual_clients.py`: example with separate subscribe and publish clients

Example with the reverse tunnel from this folder:
```bash
python3 Comms/ultra96/run_dual_clients.py \
  --host localhost \
  --port 18883 \
  --ca Comms/mosquitto/certs/ca.crt \
  --cert Comms/mosquitto/certs/clients/simulator.crt \
  --key Comms/mosquitto/certs/clients/simulator.key \
  --sub-topic esp32/voice_data \
  --pub-topic ultra96/voice_result
```

Example on the same Wi-Fi without the tunnel:
```bash
python3 Comms/ultra96/run_dual_clients.py \
  --host Yeos-MacBook-Pro.local \
  --port 8883 \
  --ca Comms/mosquitto/certs/ca.crt \
  --cert Comms/mosquitto/certs/clients/simulator.crt \
  --key Comms/mosquitto/certs/clients/simulator.key
```
