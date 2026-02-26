**Overview**
This repo uses a local Certificate Authority (CA) to sign the Mosquitto server certificate and client certificates for mutual TLS (mTLS). The TLS listener is on port `8883`, and plaintext `1883` is still enabled for local dev unless you disable it in `Comms/mosquitto/mosquitto.conf`.

**What Mutual TLS Means**
The broker presents `server.crt` to clients, and clients must also present a valid client certificate signed by the same CA. Without a client cert, the TLS handshake is rejected.

**CA Files**
- `Comms/mosquitto/certs/ca.key`: CA private key (keep secret).
- `Comms/mosquitto/certs/ca.crt`: CA public certificate (clients trust this).
- `Comms/mosquitto/certs/ca.srl`: CA serial file created by OpenSSL.

**Server Certificate Files**
- `Comms/mosquitto/certs/server.key`: Mosquitto private key.
- `Comms/mosquitto/certs/server.csr`: CSR used to request the server cert.
- `Comms/mosquitto/certs/server.crt`: Server certificate signed by the local CA.
- `Comms/mosquitto/certs/server.ext`: SAN and key usage settings for the server cert.

**Client Certificate Files**
- `Comms/mosquitto/certs/client.ext`: Key usage settings for client certs.
- `Comms/mosquitto/certs/clients/simulator.key`
- `Comms/mosquitto/certs/clients/simulator.csr`
- `Comms/mosquitto/certs/clients/simulator.crt`
- `Comms/mosquitto/certs/clients/nodered.key`
- `Comms/mosquitto/certs/clients/nodered.csr`
- `Comms/mosquitto/certs/clients/nodered.crt`
- `Comms/mosquitto/certs/clients/left_glove.key`
- `Comms/mosquitto/certs/clients/left_glove.csr`
- `Comms/mosquitto/certs/clients/left_glove.crt`
- `Comms/mosquitto/certs/clients/right_glove.key`
- `Comms/mosquitto/certs/clients/right_glove.csr`
- `Comms/mosquitto/certs/clients/right_glove.crt`
- `Comms/mosquitto/certs/clients/headset.key`
- `Comms/mosquitto/certs/clients/headset.csr`
- `Comms/mosquitto/certs/clients/headset.crt`

**Mosquitto Configuration**
TLS is configured in `Comms/mosquitto/mosquitto.conf`:
- Listener `8883` with `cafile`, `certfile`, `keyfile`
- `require_certificate true` to enforce mTLS

If you change certs, restart containers:
```bash
docker compose up -d
```

**Simulator Usage**
The simulator supports TLS + client certs:
```bash
python3 Comms/simulator/mqtt_simulator.py --tls --host localhost --port 8883
```

You can override the cert paths:
```bash
python3 Comms/simulator/mqtt_simulator.py \\
  --tls \\
  --cafile Comms/mosquitto/certs/ca.crt \\
  --certfile Comms/mosquitto/certs/clients/simulator.crt \\
  --keyfile Comms/mosquitto/certs/clients/simulator.key \\
  --host localhost --port 8883
```

If you connect by IP that is not in the server cert SANs, use `--insecure` or reissue `server.crt` with the IP in `server.ext`.

**Node-RED Usage (later step)**
When you update Node-RED, configure the broker to:
- Host: `localhost` (or your broker IP)
- Port: `8883`
- Enable TLS
- CA cert: `Comms/mosquitto/certs/ca.crt`
- Client cert: `Comms/mosquitto/certs/clients/nodered.crt`
- Client key: `Comms/mosquitto/certs/clients/nodered.key`

**Regenerating Certs**
If you regenerate the CA, you must reissue all server and client certificates and redistribute the new `ca.crt`.

Commands (run from repo root):
```bash
# Set working dir
cd Comms/mosquitto/certs

# 1) Regenerate CA
rm -f ca.key ca.crt ca.srl
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
  -subj "/CN=capstone-mosquitto-ca" -out ca.crt

# 2) Regenerate server cert
rm -f server.key server.csr server.crt
openssl genrsa -out server.key 2048
openssl req -new -key server.key -subj "/CN=mosquitto" -out server.csr
cat > server.ext <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:mosquitto,DNS:host.docker.internal
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 -extfile server.ext

# 3) Regenerate client certs (simulator + nodered)
rm -f client.ext clients/*.key clients/*.csr clients/*.crt
cat > client.ext <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF

# simulator
openssl genrsa -out clients/simulator.key 2048
openssl req -new -key clients/simulator.key -subj "/CN=simulator" -out clients/simulator.csr
openssl x509 -req -in clients/simulator.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/simulator.crt -days 825 -sha256 -extfile client.ext

# nodered
openssl genrsa -out clients/nodered.key 2048
openssl req -new -key clients/nodered.key -subj "/CN=nodered" -out clients/nodered.csr
openssl x509 -req -in clients/nodered.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/nodered.crt -days 825 -sha256 -extfile client.ext

# 4) Restart containers to pick up changes
cd ../../
docker compose up -d
```

**Why Node-RED Has a Client Cert**
Mosquitto is configured for mutual TLS (`require_certificate true`), which means every client must present a valid client certificate signed by the CA. Node-RED is a client, so it needs its own cert/key pair.

**Where Other Components Should Connect**
- Publish/subscribe clients should connect directly to the broker over TLS using their own client certs.
- Use Node-RED only if want processing/aggregation/visualization of the streams.
