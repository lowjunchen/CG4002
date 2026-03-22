#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/certs"

cd "${CERT_DIR}"

echo "Regenerating CA..."
rm -f ca.key ca.crt ca.srl
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
  -subj "/CN=capstone-mosquitto-ca" -out ca.crt

echo "Regenerating server cert..."
rm -f server.key server.csr server.crt
openssl genrsa -out server.key 2048
openssl req -new -key server.key -subj "/CN=mosquitto" -out server.csr
if [[ -f server.ext ]]; then
  echo "Using existing server.ext (no overwrite)."
else
  cat > server.ext <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:mosquitto,DNS:host.docker.internal
EOF
fi
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 -extfile server.ext

echo "Regenerating client certs..."
rm -f client.ext clients/*.key clients/*.csr clients/*.crt
mkdir -p clients
cat > client.ext <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF

openssl genrsa -out clients/simulator.key 2048
openssl req -new -key clients/simulator.key -subj "/CN=simulator" -out clients/simulator.csr
openssl x509 -req -in clients/simulator.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/simulator.crt -days 825 -sha256 -extfile client.ext

openssl genrsa -out clients/nodered.key 2048
openssl req -new -key clients/nodered.key -subj "/CN=nodered" -out clients/nodered.csr
openssl x509 -req -in clients/nodered.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/nodered.crt -days 825 -sha256 -extfile client.ext

# left_glove
openssl genrsa -out clients/left_glove.key 2048
openssl req -new -key clients/left_glove.key -subj "/CN=left_glove" -out clients/left_glove.csr
openssl x509 -req -in clients/left_glove.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/left_glove.crt -days 825 -sha256 -extfile client.ext

# right_glove
openssl genrsa -out clients/right_glove.key 2048
openssl req -new -key clients/right_glove.key -subj "/CN=right_glove" -out clients/right_glove.csr
openssl x509 -req -in clients/right_glove.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/right_glove.crt -days 825 -sha256 -extfile client.ext

# headset
openssl genrsa -out clients/headset.key 2048
openssl req -new -key clients/headset.key -subj "/CN=headset" -out clients/headset.csr
openssl x509 -req -in clients/headset.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out clients/headset.crt -days 825 -sha256 -extfile client.ext

if command -v python3 >/dev/null 2>&1; then
  echo "Updating Hardware/certs.h..."
  python3 "${SCRIPT_DIR}/export_hardware_certs.py"
else
  echo "Warning: python3 not found; Hardware/certs.h not updated."
fi

echo "Restarting containers..."
cd "${SCRIPT_DIR}/.."
docker compose up -d

echo "Done."
