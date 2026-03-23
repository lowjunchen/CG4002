"""
Debugging script: 
Subscribes to the same MQTT audio topic 
and saves the received audio as a .wav file in the data/ directory
"""
import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[4]
AI_ULTRA96_ROOT = Path(__file__).resolve().parents[2]
for search_path in (str(REPO_ROOT), str(AI_ULTRA96_ROOT)):
    if search_path not in sys.path:
        sys.path.insert(0, search_path)

from pynq_app.src.mqtt_client import MTLSMQTTClient


SAMPLE_RATE = 8000

DEFAULT_CA          = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "ca.crt"
DEFAULT_CLIENT_CERT = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "clients" / "simulator.crt"
DEFAULT_CLIENT_KEY  = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "clients" / "simulator.key"
DATA_DIR            = Path(__file__).resolve().parents[1] / "data"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture MQTT audio and save to .wav for diagnostics.")
    parser.add_argument("--mqtt-host",      default="localhost")
    parser.add_argument("--mqtt-port",      type=int, default=18883)
    parser.add_argument("--mqtt-ca",        default=str(DEFAULT_CA))
    parser.add_argument("--mqtt-cert",      default=str(DEFAULT_CLIENT_CERT))
    parser.add_argument("--mqtt-key",       default=str(DEFAULT_CLIENT_KEY))
    parser.add_argument("--mqtt-client-id", default="mic_capture_debug")
    parser.add_argument("--mqtt-username",  default="")
    parser.add_argument("--mqtt-password",  default="")
    parser.add_argument("--mqtt-sub-topic", default="audio/headset/3")
    parser.add_argument("--mqtt-tls-insecure", action="store_true")
    parser.add_argument("--duration",       type=float, default=10.0,
                        help="Seconds to capture before saving (default: 5)")
    parser.add_argument("--output",         default=None,
                        help="Output .wav path (default: data/capture_<timestamp>.wav)")
    return parser


def main(args: argparse.Namespace) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.output) if args.output else \
        DATA_DIR / f"capture_{int(time.time())}.wav"

    chunks: list[np.ndarray] = []
    pkt_count = 0

    def on_audio(client_or_payload, msg=None):
        nonlocal pkt_count
        payload = client_or_payload if msg is None else msg.payload
        raw = np.frombuffer(payload, dtype=np.uint8)
        samples = (raw.astype(np.int16) - 128) * 256
        chunks.append(samples.copy())
        pkt_count += 1
        print(f"  Packet {pkt_count:4d} | {len(samples):5d} samples | "
              f"total buffered: {sum(len(c) for c in chunks):7d}")

    mqtt_client = MTLSMQTTClient(
        client_id=args.mqtt_client_id,
        host=args.mqtt_host,
        port=args.mqtt_port,
        ca_path=args.mqtt_ca,
        cert_path=args.mqtt_cert,
        key_path=args.mqtt_key,
        username=args.mqtt_username,
        password=args.mqtt_password,
        tls_insecure=args.mqtt_tls_insecure,
    )
    mqtt_client.register_handler(args.mqtt_sub_topic, on_audio, qos=1)
    mqtt_client.connect()
    print(f"Connected. Capturing audio from '{args.mqtt_sub_topic}' "
          f"for {args.duration} s ...")

    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Interrupted early — saving what was captured so far.")
    finally:
        mqtt_client.disconnect()

    if not chunks:
        print("No audio packets received. Check that the microphone / publisher is running.")
        sys.exit(1)

    audio = np.concatenate(chunks)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # int16 → 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    duration_s = len(audio) / SAMPLE_RATE
    peak       = int(np.abs(audio).max())
    rms        = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    print(f"\nSaved {len(audio)} samples ({duration_s:.2f} s) to: {out_path}")
    print(f"  Packets received : {pkt_count}")
    print(f"  Peak amplitude   : {peak} / 32767")
    print(f"  RMS amplitude    : {rms:.1f}")
    if peak < 100:
        print("  WARNING: peak amplitude is very low — microphone may be silent or disconnected.")


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
