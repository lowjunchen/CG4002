#!/usr/bin/env python3
"""MQTT throughput stats (kbps, msgs/s)."""
from __future__ import annotations

import argparse
import collections
import time
from pathlib import Path

import paho.mqtt.client as mqtt

CERTS_DIR = Path(__file__).resolve().parents[1] / "mosquitto" / "certs"
DEFAULT_CA = CERTS_DIR / "ca.crt"
DEFAULT_CLIENT_CERT = CERTS_DIR / "clients" / "simulator.crt"
DEFAULT_CLIENT_KEY = CERTS_DIR / "clients" / "simulator.key"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MQTT throughput stats")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--topic", default="sensors/#")
    parser.add_argument("--tls", action="store_true", help="enable TLS (mTLS)")
    parser.add_argument("--cafile")
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--window", type=float, default=1.0, help="stats window in seconds")
    parser.add_argument("--print-interval", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    port = args.port if args.port is not None else (8883 if args.tls else 1883)

    client = mqtt.Client()
    if args.tls:
        cafile = str(args.cafile or DEFAULT_CA)
        certfile = str(args.certfile or DEFAULT_CLIENT_CERT)
        keyfile = str(args.keyfile or DEFAULT_CLIENT_KEY)
        client.tls_set(ca_certs=cafile, certfile=certfile, keyfile=keyfile)
        if args.insecure:
            client.tls_insecure_set(True)

    stats = collections.deque()
    total_bytes = 0
    total_msgs = 0

    def on_message(_client, _userdata, msg):
        nonlocal total_bytes, total_msgs
        now = time.time()
        # count payload bytes only
        b = len(msg.payload)
        stats.append((now, b))
        total_bytes += b
        total_msgs += 1

    client.on_message = on_message
    client.connect(args.host, port, keepalive=60)
    client.subscribe([(args.topic, 0)])
    client.loop_start()

    try:
        last_print = 0.0
        while True:
            now = time.time()
            # drop old entries
            cutoff = now - args.window
            while stats and stats[0][0] < cutoff:
                stats.popleft()

            if now - last_print >= args.print_interval:
                window_bytes = sum(b for _, b in stats)
                kbps = (window_bytes * 8) / 1000.0 / max(args.window, 1e-6)
                msgps = len(stats) / max(args.window, 1e-6)
                print(f"[stats] kbps={kbps:6.1f} msgs/s={msgps:5.1f} total_msgs={total_msgs}")
                last_print = now

            time.sleep(0.05)
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
