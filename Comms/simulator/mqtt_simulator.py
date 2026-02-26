#!/usr/bin/env python3
"""Publish simulated device telemetry to the local MQTT broker.

Topics and payloads match the hardware sketches:
  - sensors/device/1  (left glove)
  - sensors/device/2  (right glove)
  - sensors/headset/1 (headset)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    print("Missing dependency: paho-mqtt. Install with: python3 -m pip install paho-mqtt")
    sys.exit(1)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def gen_bpm(rng: random.Random) -> int:
    return int(clamp(rng.normalvariate(78, 12), 50, 130))


def gen_tier(rng: random.Random) -> int:
    return 1 if rng.random() > 0.35 else 0


def gen_percent(rng: random.Random) -> float:
    return round(clamp(rng.normalvariate(72, 15), 0, 100), 1)


def left_glove_payload(rng: random.Random) -> dict:
    bpm = gen_bpm(rng)
    return {
        "type": "left glove",
        "percent": gen_percent(rng),
        "Tier": gen_tier(rng),
        "bpm": bpm,
        "BPMAlert": 1 if bpm < 60 or bpm > 120 else 0,
    }


def right_glove_payload(rng: random.Random) -> dict:
    bpm = gen_bpm(rng)
    return {
        "type": "right glove",
        "percent": gen_percent(rng),
        "Tier": gen_tier(rng),
        "bpm": bpm,
        "BPMAlert": 1 if bpm < 60 or bpm > 120 else 0,
    }


def headset_payload(rng: random.Random) -> dict:
    voltage = clamp(rng.normalvariate(3.85, 0.08), 3.4, 4.2)
    percent = round(clamp((voltage / 3.97) * 100.0, 0, 100), 1)
    movement = rng.random() > 0.4
    return {
        "id": "1",
        "type": "headset",
        "voltage": round(voltage, 2),
        "percent": percent,
        "ax": int(rng.normalvariate(0, 8000)),
        "ay": int(rng.normalvariate(0, 8000)),
        "az": int(rng.normalvariate(16384, 8000)),
        "gx": int(rng.normalvariate(0, 4000)),
        "gy": int(rng.normalvariate(0, 4000)),
        "gz": int(rng.normalvariate(0, 4000)),
        "movement": movement,
        "p2p": int(clamp(rng.normalvariate(800, 300), 0, 4095)),
    }


def publish(client: mqtt.Client, topic: str, payload: dict) -> None:
    client.publish(topic, json.dumps(payload), qos=0, retain=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="MQTT telemetry simulator")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--client-id", default="")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--once", action="store_true", help="publish one batch and exit")
    parser.add_argument("--left-interval", type=float, default=0.5)
    parser.add_argument("--right-interval", type=float, default=0.5)
    parser.add_argument("--headset-interval", type=float, default=0.2)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    client = mqtt.Client(client_id=args.client_id or None)
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    next_left = 0.0
    next_right = 0.0
    next_headset = 0.0

    try:
        while True:
            now = time.time()

            if now >= next_left:
                publish(client, "sensors/device/1", left_glove_payload(rng))
                next_left = now + max(args.left_interval, 0.01)

            if now >= next_right:
                publish(client, "sensors/device/2", right_glove_payload(rng))
                next_right = now + max(args.right_interval, 0.01)

            if now >= next_headset:
                publish(client, "sensors/headset/1", headset_payload(rng))
                next_headset = now + max(args.headset_interval, 0.01)

            if args.once:
                break

            time.sleep(0.01)
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
