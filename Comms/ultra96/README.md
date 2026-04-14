# Ultra96 Tunnel Guide

Use this folder when the Ultra96 can SSH out but cannot reach the MQTT broker directly.

The current working path is:

1. Run the reverse SSH tunnel from the laptop.
2. Connect the Ultra96 MQTT client to `localhost:18883`.
3. Authenticate with `Comms/mosquitto/certs/ca.crt`, `ultra96fpga.crt`, and `ultra96fpga.key`.

## Files

- `ssh_tunnel.sh`: primary tunnel launcher for macOS/Linux.
- `ssh_tunnel.bat`: Windows equivalent.
- `tunnel.env.example`: config template.
- `mqtt_client.py`: reusable Python MQTT/TLS wrapper.

## Recommended Setup: Reverse Tunnel

Copy the template:

```bash
cp Comms/ultra96/tunnel.env.example Comms/ultra96/tunnel.env
```

Set these values in `Comms/ultra96/tunnel.env`:

```bash
MODE=reverse
TUNNEL_USER=xilinx
TUNNEL_HOST=<ultra96-ssh-host>
TUNNEL_PORT=22

REVERSE_TARGET_HOST=<broker-reachable-from-laptop>
REVERSE_TARGET_PORT=8883
REMOTE_BIND_ADDR=127.0.0.1
REMOTE_PORT=18883
```

Start the tunnel from the laptop:

```bash
MODE=reverse Comms/ultra96/ssh_tunnel.sh
```

On the Ultra96, the broker should now be reachable at:

- host: `localhost`
- port: `18883`

Smoke-test the tunnel from the Ultra96 with the simulator:

```bash
python3 Comms/simulator/mqtt_simulator.py \
  --tls \
  --host localhost \
  --port 18883 \
  --cafile Comms/mosquitto/certs/ca.crt \
  --certfile Comms/mosquitto/certs/clients/ultra96fpga.crt \
  --keyfile Comms/mosquitto/certs/clients/ultra96fpga.key
```

If you are writing Ultra96-side code, reuse `Comms/ultra96/mqtt_client.py` instead of duplicating TLS setup.

## Optional Setup: Forward Tunnel

`ssh_tunnel.sh` still supports `MODE=forward`, but that is not the main documented deployment path anymore.

Use it only if the Ultra96 should open a local port that forwards to a remote broker:

```bash
MODE=forward Comms/ultra96/ssh_tunnel.sh
```

Relevant variables:

- `LOCAL_PORT`
- `BROKER_HOST`
- `BROKER_PORT`

## Notes

- `autossh` is used automatically if it is installed.
- The reverse tunnel binds to `127.0.0.1` by default for safety.
- If TLS hostname verification fails against `localhost`, either reissue the server certificate with the correct SANs or use client-side insecure mode only for temporary testing.

## Troubleshooting

- No listener on Ultra96: the reverse tunnel is not running or exited.
- `Connection reset`: `REVERSE_TARGET_HOST` or `REVERSE_TARGET_PORT` is wrong.
- TLS handshake failure: the Ultra96 certs do not match the broker CA, or the broker hostname does not match the certificate SAN.
