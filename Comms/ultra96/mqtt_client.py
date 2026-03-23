#!/usr/bin/env python3
import json
import logging
import ssl
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

import paho.mqtt.client as mqtt


MessageHandler = Callable[[mqtt.Client, mqtt.MQTTMessage], None]


def _create_client(client_id: str) -> mqtt.Client:
    callback_api = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api is not None:
        return mqtt.Client(callback_api.VERSION1, client_id=client_id)
    return mqtt.Client(client_id=client_id)


class MTLSMQTTClient:
    def __init__(
        self,
        *,
        client_id: str,
        host: str,
        port: int,
        ca_path: str,
        cert_path: str,
        key_path: str,
        username: str = "",
        password: str = "",
        keepalive: int = 60,
        tls_insecure: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.client_id = client_id
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.logger = logger or logging.getLogger(client_id)
        self._connected = threading.Event()
        self._subscriptions: Dict[str, int] = {}
        self._handlers: Dict[str, MessageHandler] = {}
        self._intentional_disconnect = False

        self._client = _create_client(client_id)
        self._client.enable_logger(self.logger)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

        if username or password:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        ca_file = Path(ca_path)
        cert_file = Path(cert_path)
        key_file = Path(key_path)
        for path in (ca_file, cert_file, key_file):
            if not path.exists():
                raise FileNotFoundError(f"Missing TLS file: {path}")

        self._client.tls_set(
            ca_certs=str(ca_file),
            certfile=str(cert_file),
            keyfile=str(key_file),
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.tls_insecure_set(tls_insecure)

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            self.logger.error("MQTT connect failed rc=%s", rc)
            self._connected.clear()
            return

        self.logger.info("MQTT connected to %s:%s", self.host, self.port)
        self._connected.set()
        for topic, qos in self._subscriptions.items():
            client.subscribe(topic, qos=qos)

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if self._intentional_disconnect:
            self.logger.info("MQTT disconnected cleanly")
            return
        self.logger.warning("MQTT disconnected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        handler = self._handlers.get(msg.topic)
        if handler is None:
            self.logger.debug("Unhandled topic %s (%d bytes)", msg.topic, len(msg.payload))
            return
        handler(client, msg)

    def register_handler(self, topic: str, handler: MessageHandler, qos: int = 0) -> None:
        self._handlers[topic] = handler
        self._subscriptions[topic] = qos
        if self._connected.is_set():
            self._client.subscribe(topic, qos=qos)

    def connect(self, wait_timeout: float = 10.0) -> None:
        self._intentional_disconnect = False
        self._client.connect(self.host, self.port, keepalive=self.keepalive)
        self._client.loop_start()
        if not self._connected.wait(wait_timeout):
            raise TimeoutError(
                f"Timed out waiting for MQTT connect: {self.host}:{self.port} ({self.client_id})"
            )

    def disconnect(self) -> None:
        self._intentional_disconnect = True
        self._client.loop_stop()
        self._client.disconnect()

    def publish(
        self,
        topic: str,
        payload,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, separators=(",", ":"))
        info = self._client.publish(topic, payload, qos=qos, retain=retain)
        info.wait_for_publish()
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Publish failed for {topic} rc={info.rc}")
