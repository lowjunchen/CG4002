#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/certs"

cd "${CERT_DIR}"

for required in ca.key ca.crt server.ext; do
  if [[ ! -f "${required}" ]]; then
    echo "Missing ${required} in ${CERT_DIR}." >&2
    echo "Keep the existing CA, update server.ext, then rerun this script." >&2
    exit 1
  fi
done

echo "Reissuing server certificate with existing CA..."
if [[ ! -f server.key ]]; then
  echo "server.key not found; generating a new server key."
  openssl genrsa -out server.key 2048
fi
rm -f server.csr server.crt
openssl req -new -key server.key -subj "/CN=mosquitto" -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 -extfile server.ext

echo "Restarting Mosquitto..."
cd "${SCRIPT_DIR}/.."
docker compose up -d mosquitto

echo "Done."
echo "CA and client certs were unchanged, so Hardware/certs.h does not need to be regenerated or reflashed."
