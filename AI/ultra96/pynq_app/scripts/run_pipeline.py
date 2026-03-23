#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
AI_ULTRA96_ROOT = Path(__file__).resolve().parents[2]
for search_path in (str(REPO_ROOT), str(AI_ULTRA96_ROOT)):
    if search_path not in sys.path:
        sys.path.insert(0, search_path)

from pynq import PL

from pynq_app.src.audio_buffer import AudioBuffer
from pynq_app.src.inference import run_inference_on_windows
from pynq_app.src.mqtt_client import MTLSMQTTClient
from pynq_app.src.mqtt_handlers import VoiceDataCollector
from pynq_app.src.overlay_loader import load_overlay
from pynq_app.src.power_manager import apply_profile


SAMPLE_RATE = 8000
WINDOW_SIZE = SAMPLE_RATE * 1
HOP_SIZE = SAMPLE_RATE // 2

DEFAULT_CA = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "ca.crt"
DEFAULT_CLIENT_CERT = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "clients" / "simulator.crt"
DEFAULT_CLIENT_KEY = REPO_ROOT / "Comms" / "mosquitto" / "certs" / "clients" / "simulator.key"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Ultra96 inference pipeline over MQTT.")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=18883)
    parser.add_argument("--mqtt-ca", default=str(DEFAULT_CA))
    parser.add_argument("--mqtt-cert", default=str(DEFAULT_CLIENT_CERT))
    parser.add_argument("--mqtt-key", default=str(DEFAULT_CLIENT_KEY))
    parser.add_argument("--mqtt-client-id", default="ultra96")
    parser.add_argument("--mqtt-username", default="")
    parser.add_argument("--mqtt-password", default="")
    parser.add_argument("--mqtt-sub-topic", default="audio/headset/1")
    parser.add_argument("--mqtt-pub-topic", default="ai/ultra96/result")
    parser.add_argument("--mqtt-tls-insecure", action="store_true")
    parser.add_argument("--min-samples", type=int, default=WINDOW_SIZE)
    parser.add_argument("--pre-profile", choices=["performance", "powersave"], default="performance")
    parser.add_argument("--post-profile", choices=["performance", "powersave"], default="powersave")
    return parser


def main(args: argparse.Namespace) -> None:
    apply_profile(args.pre_profile)

    PL.reset()
    _, dma = load_overlay()
    print("Overlay and DMA loaded.")

    audio_buf = AudioBuffer(window_size=WINDOW_SIZE, hop_size=HOP_SIZE)
    collector = VoiceDataCollector(audio_buf)

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
    mqtt_client.register_handler(args.mqtt_sub_topic, collector.voice_data_handler, qos=1)
    mqtt_client.connect()
    print(f"MQTT connected, waiting for packets on {args.mqtt_sub_topic}...")

    try:
        while True:
            if collector.is_ready(min_samples=args.min_samples):
                windows = audio_buf.get_windows()

                if len(windows) == 0:
                    out_pkt = {"status": "FAILED", "info": "Insufficient audio data"}
                    print("No complete windows available.")
                else:
                    print(f"Running inference on {len(windows)} overlapping windows...")
                    best_label, best_confidence = run_inference_on_windows(windows, dma)
                    out_pkt = {
                        "status": "SUCCESS",
                        "result": best_label,
                        "confidence": best_confidence,
                        "windows": len(windows),
                    }

                collector.reset()
                json_pkt = json.dumps(out_pkt)
                mqtt_client.publish(args.mqtt_pub_topic, json_pkt, qos=1)
                print(f"Published on {args.mqtt_pub_topic}: {json_pkt}")

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Shut down by user.")
    finally:
        mqtt_client.disconnect()
        apply_profile(args.post_profile)


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
