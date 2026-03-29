**README — Ultra96 Connection**
This doc captures the working setup for sending MQTT data from an Ultra96 (on a restricted network) to the laptop‑hosted Mosquitto broker using an SSH reverse tunnel.

---

**What’s running where**
- **Laptop**: Mosquitto broker (TLS on `8883`, optional plaintext on `1883`)
- **Ultra96**: MQTT client (e.g., `Comms/simulator/mqtt_simulator.py`)
- **Tunnel**: reverse SSH tunnel **from laptop → Ultra96**

---

**1. Start the broker on the laptop**
```bash
cd Comms
docker compose up -d
```

Optional check:
```bash
docker ps --filter name=mosquitto --filter name=nodered
```

---

**2. Make sure Ultra96 has the repo and certs**
On Ultra96, verify the certs exist (from repo clone):
```bash
ls -l Comms/mosquitto/certs/ca.crt
ls -l Comms/mosquitto/certs/clients/simulator.crt
ls -l Comms/mosquitto/certs/clients/simulator.key
```

If missing, copy from laptop. Do **not** regenerate certs on Ultra96 unless you also regenerate them on the broker.

---

**3. Reverse SSH tunnel (run on laptop)**
We open a port on Ultra96 (`18883`) that forwards to a broker reachable from the laptop. This can be the laptop's local broker or the AWS broker.

Edit `Comms/ultra96/tunnel.env` **on your laptop**:
```
MODE=reverse
TUNNEL_USER=xilinx
TUNNEL_HOST=makerslab-fpga-33.ddns.comp.nus.edu.sg
TUNNEL_PORT=22

# Reverse target reachable from the laptop
REVERSE_TARGET_HOST=18.140.9.0
REVERSE_TARGET_PORT=8883

# Port exposed on Ultra96
REMOTE_BIND_ADDR=127.0.0.1
REMOTE_PORT=18883
```

Start the tunnel (on laptop) after giving permission with chmod +x ssh_tunnel.sh:
```bash
MODE=reverse Comms/ultra96/ssh_tunnel.sh
or
MODE=reverse ./ssh_tunnel.sh

```

Leave this running.

Ultra96 should now have a local listener:
```bash
ss -ltnp | grep 18883
```

---

**4. Run the simulator on Ultra96**
```bash
python3 Comms/simulator/mqtt_simulator.py --tls --host localhost --port 18883
```

If you still want to proxy to a broker running on the laptop itself, set:
```bash
REVERSE_TARGET_HOST=localhost
REVERSE_TARGET_PORT=8883
```

---

**5. Verify on laptop**
TLS check (recommended):
```bash
docker exec mosquitto sh -c 'mosquitto_sub -h localhost -p 8883 \
  --cafile /mosquitto/config/certs/ca.crt \
  --cert /mosquitto/config/certs/clients/simulator.crt \
  --key /mosquitto/config/certs/clients/simulator.key \
  -t "sensors/#"'
```

Plaintext check (only if `1883` is enabled):
```bash
docker exec mosquitto sh -c 'mosquitto_sub -h localhost -p 1883 -t "sensors/#"'
```

---

**6. Node‑RED visibility**
Node‑RED already subscribes to the broker. Ensure the **Mosquitto Inputs** tab is enabled:
- Open `http://localhost:1880`
- Click the “Toggle Broker” inject node (switches HiveMQ ↔ Mosquitto)
- You can see the data coming in as well

---

**Common issues**
- **Connection reset** on Ultra96: tunnel forwarding to the wrong broker target.  
  Make sure `REVERSE_TARGET_HOST` and `REVERSE_TARGET_PORT` point to the broker the laptop can reach.
- **No listener on Ultra96**: reverse tunnel not running or exited.
- **TLS handshake fails**: certs on Ultra96 don’t match broker CA.
  Compare hashes:
  ```bash
  sha256sum Comms/mosquitto/certs/ca.crt Comms/mosquitto/certs/clients/simulator.crt
  ```
