#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/certs"
CLIENTS_DIR="${CERT_DIR}/clients"

NAME="${1:-unity_pub}"
PFX_PASS="${PFX_PASS:-capstone}"
PFX_LEGACY="${PFX_LEGACY:-0}"

cd "${CERT_DIR}"

if [[ ! -f ca.crt || ! -f ca.key ]]; then
  echo "Missing ca.crt/ca.key in ${CERT_DIR}. Run regen_certs.sh first." >&2
  exit 1
fi

mkdir -p "${CLIENTS_DIR}"

KEY_PATH="${CLIENTS_DIR}/${NAME}.key"
CSR_PATH="${CLIENTS_DIR}/${NAME}.csr"
CRT_PATH="${CLIENTS_DIR}/${NAME}.crt"
PFX_PATH="${CLIENTS_DIR}/${NAME}.pfx"
EXT_PATH="${CERT_DIR}/client.ext"

if [[ ! -f "${EXT_PATH}" ]]; then
  cat > "${EXT_PATH}" <<'EXT'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EXT
fi

openssl genrsa -out "${KEY_PATH}" 2048
openssl req -new -key "${KEY_PATH}" -subj "/CN=${NAME}" -out "${CSR_PATH}"
openssl x509 -req -in "${CSR_PATH}" -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out "${CRT_PATH}" -days 825 -sha256 -extfile "${EXT_PATH}"

LEGACY_ARGS=()
if [[ "${PFX_LEGACY}" == "1" ]]; then
  LEGACY_ARGS=(-legacy -macalg sha1 -certpbe PBE-SHA1-3DES -keypbe PBE-SHA1-3DES)
fi

openssl pkcs12 "${LEGACY_ARGS[@]}" -export -out "${PFX_PATH}" \
  -inkey "${KEY_PATH}" -in "${CRT_PATH}" -certfile ca.crt \
  -passout pass:"${PFX_PASS}"

chmod 600 "${KEY_PATH}" "${PFX_PATH}"

cat <<MSG
Generated client certs:
- ${CRT_PATH}
- ${KEY_PATH}
- ${PFX_PATH}
PFX password: ${PFX_PASS}
PFX legacy mode: ${PFX_LEGACY}
MSG
