import time
import ssl
import json
import paho.mqtt.client as mqtt
from pathlib import Path
from config import CERT_NAME

class MQTTClient:
    """
    MQTT client implementation with TLS security
    """
    def __init__(self, username, password, host, port, client_id, cert_dir=None):
        self.host = host
        self.port = port
        self._intentional_disconnect = False
        self._topic_handlers = {}

        self._client = mqtt.Client(client_id=client_id)
        self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        self._cert_dir = cert_dir or Path(__file__).resolve().parent / "devices"
        self._load_certificates()
    
    def _load_certificates(self):
        ca_path = self._cert_dir / f"{CERT_NAME}ca.crt"
        client_cert = self._cert_dir / f"{CERT_NAME}client.crt"
        client_key = self._cert_dir / f"{CERT_NAME}client.key"

        for path in (ca_path, client_cert, client_key):
            if not path.exists():
                raise FileNotFoundError(f"Missing certificate: {path}")

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_ctx.load_verify_locations(str(ca_path))
        ssl_ctx.load_cert_chain(str(client_cert), str(client_key))
        self._client.tls_set_context(ssl_ctx)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to broker.")
            for topic in self._topic_handlers:
                self._client.subscribe(topic)
        else:
            print(f"Connection failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        if self._intentional_disconnect:
            print("Disconnected by user.")
            return

        print(f"Unexpected disconnect (rc={rc}). Reconnecting...")
        delay = 1
        while not self._intentional_disconnect:
            try:
                self._client.reconnect()
                print("Reconnected successfully.")
                return
            except Exception as exc:
                print(f"Reconnect failed ({exc}), retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 30)

    def _on_message(self, client, userdata, msg):
        handler = self._topic_handlers.get(msg.topic)
        if handler is not None:
            handler(msg.payload)

    def register_handler(self, topic, handler, qos=0):
        self._topic_handlers[topic] = handler
        self._client.subscribe(topic, qos)

    def connect(self):
        self._intentional_disconnect = False
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()

    def disconnect(self):
        self._intentional_disconnect = True
        self._client.loop_stop()
        self._client.disconnect()
        print("Disconnected from broker.")

    def publish(self, topic, payload, qos=0, retain=False):
        rc, _ = self._client.publish(topic, payload, qos=qos, retain=retain)
        if rc != 0:
            print(f"Publish failed on topic {topic} (rc={rc})")
            