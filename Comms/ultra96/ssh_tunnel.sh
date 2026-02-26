#!/usr/bin/env bash
set -euo pipefail

# Load env file if present
ENV_FILE="${ENV_FILE:-$(dirname "$0")/tunnel.env}"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

MODE="${MODE:-forward}"               # forward or reverse
TUNNEL_USER="${TUNNEL_USER:-}"
TUNNEL_HOST="${TUNNEL_HOST:-}"
TUNNEL_PORT="${TUNNEL_PORT:-22}"

# Forward mode: Ultra96 publishes to a remote broker via local port forwarding.
LOCAL_PORT="${LOCAL_PORT:-18883}"     # local port on Ultra96
BROKER_HOST="${BROKER_HOST:-localhost}"
BROKER_PORT="${BROKER_PORT:-8883}"

# Reverse mode: expose Ultra96 local broker to remote host.
REMOTE_BIND_ADDR="${REMOTE_BIND_ADDR:-127.0.0.1}"
REMOTE_PORT="${REMOTE_PORT:-18883}"   # port opened on remote host

if [[ -z "${TUNNEL_USER}" || -z "${TUNNEL_HOST}" ]]; then
  echo "Missing TUNNEL_USER or TUNNEL_HOST. Update tunnel.env." >&2
  exit 1
fi

SSH_BASE=(ssh -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -p "${TUNNEL_PORT}")

if command -v autossh >/dev/null 2>&1; then
  SSH_CMD=(autossh -M 0 "${SSH_BASE[@]}")
else
  SSH_CMD=("${SSH_BASE[@]}")
fi

case "${MODE}" in
  forward)
    echo "Starting forward tunnel: localhost:${LOCAL_PORT} -> ${BROKER_HOST}:${BROKER_PORT} via ${TUNNEL_HOST}"
    exec "${SSH_CMD[@]}" -L "${LOCAL_PORT}:${BROKER_HOST}:${BROKER_PORT}" "${TUNNEL_USER}@${TUNNEL_HOST}"
    ;;
  reverse)
    echo "Starting reverse tunnel: ${TUNNEL_HOST}:${REMOTE_PORT} -> localhost:${LOCAL_PORT}"
    exec "${SSH_CMD[@]}" -R "${REMOTE_BIND_ADDR}:${REMOTE_PORT}:localhost:${LOCAL_PORT}" "${TUNNEL_USER}@${TUNNEL_HOST}"
    ;;
  *)
    echo "Unknown MODE=${MODE}. Use 'forward' or 'reverse'." >&2
    exit 1
    ;;
esac
