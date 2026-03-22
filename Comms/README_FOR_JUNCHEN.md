**Hardware MQTT TLS Setup**
This guide is for running the broker on your laptop and connecting the ESP32 hardware over mutual TLS (mTLS).

**1. Start the Broker (on your laptop)**
1. Open a terminal in the repo.
2. Run:
```bash
cd Comms
docker compose up -d
```
3. Confirm containers are up:
```bash
docker ps --filter name=mosquitto --filter name=nodered
```

**2. Certificates (already set up)**
Client and CA certs live in `Comms/mosquitto/certs/`. I already uploaded for now for development. The device client certs are embedded into `Hardware/certs.h`, so you do not need to copy cert files to the ESP32.

If certs are missing (fresh clone) or you update the server IP:
1. Edit `Comms/mosquitto/certs/server.ext` and add your laptop IP to `subjectAltName`.
2. Regenerate certs and update `Hardware/certs.h`:
```bash
Comms/mosquitto/regen_certs.sh
```

**3. Set the broker host in each sketch**
Update the broker host in each `.ino` file to your laptop LAN IP:
- `Hardware/Left_Glove/Left_Glove.ino`
- `Hardware/Right_Glove/Right_Glove.ino`
- `Hardware/Headset/Headset.ino`

Example:
```cpp
const char* mqttServer = "192.168.0.10"; // your laptop LAN IP
const int mqttPort = 8883;               // TLS port
```

**4. Flash the devices**
1. Open each sketch in Arduino IDE (or use `arduino-cli`).
2. Select the correct ESP32 board and port.
3. Build and upload.

**5. Verify it works**
1. Open Serial Monitor at `115200`.
2. You should see “WiFi connected” then “Connecting MQTT... connected”.
3. Optional broker check:
```bash
docker exec mosquitto sh -c 'mosquitto_sub -h localhost -p 8883 --cafile /mosquitto/config/certs/ca.crt --cert /mosquitto/config/certs/clients/simulator.crt --key /mosquitto/config/certs/clients/simulator.key -t "sensors/#"'
```

**Notes**
- Node-RED is optional. If you want visualization/processing, enable the Mosquitto inputs tab in Node-RED.
- All hardware connects directly to the broker. Node-RED is not a required hop.

---

**Ultra96 SSH Tunnel (when MQTT is blocked)**
If the Ultra96 cannot reach the broker directly, use the SSH tunnel script:
- Docs: `Comms/ultra96/README.md`
- Script: `Comms/ultra96/ssh_tunnel.sh`
