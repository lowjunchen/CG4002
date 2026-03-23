from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_COMMS_MQTT_CLIENT = Path(__file__).resolve().parents[4] / "Comms" / "ultra96" / "mqtt_client.py"
if not _COMMS_MQTT_CLIENT.exists():
    raise FileNotFoundError(f"Missing shared MQTT client implementation: {_COMMS_MQTT_CLIENT}")

_spec = spec_from_file_location("comms_ultra96_mqtt_client", _COMMS_MQTT_CLIENT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load MQTT client module from {_COMMS_MQTT_CLIENT}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

MTLSMQTTClient = _module.MTLSMQTTClient

# Backward-compatible aliases for the previous AI-side naming.
MQTTClient = MTLSMQTTClient
SecureMQTTClient = MTLSMQTTClient

__all__ = ["MTLSMQTTClient", "MQTTClient", "SecureMQTTClient"]
