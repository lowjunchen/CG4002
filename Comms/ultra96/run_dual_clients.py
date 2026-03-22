#!/usr/bin/env python3
import argparse
import json
import logging
import signal
import threading
import time
from pathlib import Path

from mqtt_client import MTLSMQTTClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ultra96 MQTT example with separate subscriber and publisher clients."
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=18883)
    parser.add_argument("--ca", default="Comms/mosquitto/certs/ca.crt")
    parser.add_argument("--cert", default="Comms/mosquitto/certs/clients/simulator.crt")
    parser.add_argument("--key", default="Comms/mosquitto/certs/clients/simulator.key")
    parser.add_argument("--sub-topic", default="audio/headset/1")
    parser.add_argument("--pub-topic", default="ai/ultra96/result")
    parser.add_argument("--tls-insecure", action="store_true")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ca = Path(args.ca)
    cert = Path(args.cert)
    key = Path(args.key)

    stop_event = threading.Event()

    pub_client = MTLSMQTTClient(
        client_id="ultra96-pub",
        host=args.host,
        port=args.port,
        ca_path=str(ca),
        cert_path=str(cert),
        key_path=str(key),
        username=args.username,
        password=args.password,
        tls_insecure=args.tls_insecure,
        logger=logging.getLogger("ultra96-pub"),
    )

    def on_message(client, msg) -> None:
        try:
            payload_text = msg.payload.decode("utf-8")
            payload_kind = "utf8"
        except UnicodeDecodeError:
            payload_text = msg.payload.hex()
            payload_kind = "hex"

        out_msg = {
            "status": "RECEIVED",
            "source_topic": msg.topic,
            "payload_kind": payload_kind,
            "payload_size": len(msg.payload),
            "payload": payload_text,
            "ts": time.time(),
        }
        pub_client.publish(args.pub_topic, out_msg, qos=1)
        logging.getLogger("ultra96-sub").info(
            "Forwarded %d bytes from %s to %s",
            len(msg.payload),
            msg.topic,
            args.pub_topic,
        )

    sub_client = MTLSMQTTClient(
        client_id="ultra96-sub",
        host=args.host,
        port=args.port,
        ca_path=str(ca),
        cert_path=str(cert),
        key_path=str(key),
        username=args.username,
        password=args.password,
        tls_insecure=args.tls_insecure,
        logger=logging.getLogger("ultra96-sub"),
    )
    sub_client.register_handler(args.sub_topic, on_message, qos=1)

    def handle_stop(signum, frame) -> None:
        logging.info("Stopping on signal %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    pub_client.connect()
    sub_client.connect()
    logging.info(
        "Dual MQTT clients ready: subscribe=%s publish=%s broker=%s:%s",
        args.sub_topic,
        args.pub_topic,
        args.host,
        args.port,
    )

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        sub_client.disconnect()
        pub_client.disconnect()


if __name__ == "__main__":
    main()
