# Capstone mTLS Notes

This file is the short conceptual companion to [CERTS.md](/Users/yeoyao/Github_NEW/capstone/Comms/mosquitto/CERTS.md:1). Use `CERTS.md` for commands and certificate operations; use this file when you need the mental model.

## What mTLS Means Here

On broker port `8883`:

1. Mosquitto presents `server.crt`.
2. The client verifies `server.crt` against `ca.crt`.
3. The client presents its own client certificate.
4. Mosquitto verifies that client certificate against the same `ca.crt`.

That is mutual TLS: both sides authenticate each other before MQTT traffic starts.

## The Important Files

### CA

- `ca.key`: secret signing key
- `ca.crt`: public trust anchor

### Broker

- `server.key`: broker private key
- `server.crt`: broker identity certificate
- `server.ext`: broker SAN and usage settings

### Client

For each client such as `headset`, `left_glove`, `unity_pub`, or `ultra96fpga`:

- `<name>.key`: private key
- `<name>.csr`: issue-time certificate request
- `<name>.crt`: signed client certificate
- `<name>.pfx`: optional packaged format used by consumers such as Unity

## Who Holds What

- Broker: `ca.crt`, `server.crt`, `server.key`
- ESP32 hardware: CA plus per-device cert/key embedded in `Hardware/certs.h`
- Ultra96: `ca.crt`, `ultra96fpga.crt`, `ultra96fpga.key`
- Unity: `ca.crt`, `unity_pub.pfx`

Never distribute `ca.key` outside the signing environment.

## Why Both Sides Need `ca.crt`

- Clients use `ca.crt` to verify the broker certificate.
- Mosquitto uses `ca.crt` to verify client certificates.

`ca.crt` is public. `ca.key` is not.

## Why Hostnames Matter

TLS does not only check who signed the broker certificate. It also checks whether the hostname or IP you connected to appears in the broker certificate SAN list.

That means:

- if the broker host changes to a new IP or DNS name, update `server.ext`
- then run `reissue_server_cert.sh`

If the CA and client certs stay the same, hardware does not need to be reflashed.

## CSR in One Line

A CSR is only an issue-time request:

```text
client.key -> client.csr -> signed by CA -> client.crt
```

It is not a runtime credential.

## Hardware-Specific Note

The ESP32 devices do not load `.crt` and `.key` files from disk. Their CA cert, client cert, and private key are embedded into `Hardware/certs.h` and compiled into firmware.

That is why a full CA or client-cert regeneration requires reflashing hardware.
