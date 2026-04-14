# Certificate Operations

This folder owns the local CA, the Mosquitto server certificate, and all MQTT client certificates used by the project.

The broker TLS listener is `8883`. Mutual TLS is enforced there with `require_certificate true` in [mosquitto.conf](/Users/yeoyao/Github_NEW/capstone/Comms/mosquitto/mosquitto.conf:1).

## Active Client Identities

- `ultra96fpga`
- `headset`
- `left_glove`
- `right_glove`
- `nodered`
- `laptop_pub`
- `unity_pub`

## File Roles

### CA

- `ca.key`: private signing key. Keep secret.
- `ca.crt`: public CA certificate distributed to clients and broker.
- `ca.srl`: OpenSSL serial counter.

### Broker

- `server.key`: Mosquitto private key.
- `server.csr`: broker CSR.
- `server.crt`: broker certificate signed by the CA.
- `server.ext`: SAN and key-usage settings for the broker cert.

### Clients

For each client in `certs/clients/`:

- `<name>.key`: private key
- `<name>.csr`: certificate signing request
- `<name>.crt`: signed client certificate
- `<name>.pfx`: PKCS#12 bundle for consumers such as Unity

## Who Uses What

- Mosquitto: `ca.crt`, `server.crt`, `server.key`
- ESP32 hardware: CA plus device cert/key embedded into `Hardware/certs.h`
- Ultra96: `ca.crt`, `ultra96fpga.crt`, `ultra96fpga.key`
- Unity: `ca.crt`, `unity_pub.pfx`
- Node-RED: `ca.crt`, `nodered.crt`, `nodered.key`

## Common Tasks

### Create or rotate one client identity

From `Comms/mosquitto`:

```bash
./gen_client_cert.sh <client_name>
```

Example:

```bash
PFX_PASS=capstone PFX_LEGACY=1 ./gen_client_cert.sh unity_pub
```

### Reissue only the broker certificate

Use this when the broker hostname or IP SANs changed but the CA should stay the same.

1. Edit `Comms/mosquitto/certs/server.ext`.
2. Reissue the server certificate:

```bash
./reissue_server_cert.sh
```

This keeps all client certs valid. Hardware does not need reflashing.

### Regenerate everything

Use this only when you want a new CA and a full certificate reset:

```bash
./regen_certs.sh
```

Effects:

- replaces the CA
- reissues broker and client certs
- rewrites `Hardware/certs.h`
- requires ESP32 devices to be reflashed
- restarts the broker container

## Verification

Subscribe over TLS with the Ultra96 identity:

```bash
docker exec mosquitto sh -c 'mosquitto_sub -h localhost -p 8883 \
  --cafile /mosquitto/config/certs/ca.crt \
  --cert /mosquitto/config/certs/clients/ultra96fpga.crt \
  --key /mosquitto/config/certs/clients/ultra96fpga.key \
  -t "sensors/#"'
```

If hostname verification fails, either connect using a name present in `server.ext` or reissue the server certificate after updating the SANs.

For the certificate concepts behind these files, see [MTLS_EXPLAINER.md](/Users/yeoyao/Github_NEW/capstone/Comms/mosquitto/MTLS_EXPLAINER.md:1).
