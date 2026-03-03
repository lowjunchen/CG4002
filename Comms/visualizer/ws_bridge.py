#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import ssl
import time
from typing import Optional, Set

import paho.mqtt.client as mqtt
import websockets


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bridge MQTT topics to WebSocket clients.")
    p.add_argument("--mqtt-host", default="127.0.0.1")
    p.add_argument("--mqtt-port", type=int, default=1883)
    p.add_argument("--mqtt-topic", default="sensors/#")
    p.add_argument("--mqtt-tls", action="store_true")
    p.add_argument("--ca", default="")
    p.add_argument("--cert", default="")
    p.add_argument("--key", default="")
    p.add_argument("--tls-insecure", action="store_true")
    p.add_argument("--ws-host", default="0.0.0.0")
    p.add_argument("--ws-port", type=int, default=8765)
    p.add_argument("--ws-to-mqtt-topic", default="")
    p.add_argument("--log-level", default="INFO")
    return p


class Bridge:
    def __init__(self, args: argparse.Namespace, loop: asyncio.AbstractEventLoop) -> None:
        self.args = args
        self.loop = loop
        self.clients: Set[websockets.WebSocketServerProtocol] = set()

        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = self._on_message

        if self.args.mqtt_tls:
            self._configure_tls()

    def _configure_tls(self) -> None:
        if not self.args.ca:
            raise SystemExit("--ca is required when --mqtt-tls is set")
        self.mqtt.tls_set(
            ca_certs=self.args.ca,
            certfile=self.args.cert or None,
            keyfile=self.args.key or None,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        if self.args.tls_insecure:
            self.mqtt.tls_insecure_set(True)

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logging.error("MQTT connect failed rc=%s", rc)
            return
        logging.info("MQTT connected. Subscribing to %s", self.args.mqtt_topic)
        client.subscribe(self.args.mqtt_topic)

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = msg.payload.hex()

        data = {
            "topic": msg.topic,
            "payload": payload,
            "ts": time.time(),
        }
        text = json.dumps(data, separators=(",", ":"))
        asyncio.run_coroutine_threadsafe(self._broadcast(text), self.loop)

    async def _broadcast(self, text: str) -> None:
        if not self.clients:
            return
        dead = []
        for ws in self.clients:
            try:
                await ws.send(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def ws_handler(self, ws: websockets.WebSocketServerProtocol):
        self.clients.add(ws)
        logging.info("WS client connected (%d total)", len(self.clients))
        try:
            async for message in ws:
                if not self.args.ws_to_mqtt_topic:
                    continue
                self.mqtt.publish(self.args.ws_to_mqtt_topic, message)
        finally:
            self.clients.discard(ws)
            logging.info("WS client disconnected (%d total)", len(self.clients))

    def start_mqtt(self) -> None:
        logging.info("Connecting MQTT %s:%s", self.args.mqtt_host, self.args.mqtt_port)
        self.mqtt.connect(self.args.mqtt_host, self.args.mqtt_port, keepalive=60)
        self.mqtt.loop_start()


async def main() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    loop = asyncio.get_running_loop()
    bridge = Bridge(args, loop)
    bridge.start_mqtt()

    logging.info("Starting WebSocket server on %s:%s", args.ws_host, args.ws_port)
    async with websockets.serve(bridge.ws_handler, args.ws_host, args.ws_port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
