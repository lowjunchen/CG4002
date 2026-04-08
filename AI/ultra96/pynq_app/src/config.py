from pathlib import Path

_ULTRA96_ROOT = Path(__file__).resolve().parents[2]  # AI/ultra96/
OVERLAY_BIT = str(_ULTRA96_ROOT / "overlay" / "kws.bit")

DMA_NAME = "axi_dma_0"
ACCEL_NAME = "kws_top_0"

#AXIS config
AXIS_W = 32
BYTES_PER_BEAT = 4

#MFCC input
IN_LEN = 1274

#Logits output
OUT_LEN = 7

#Confidence tolerance
CONFIDENCE_TOLERANCE = 0.50

#Cert name for MQTT
CERT_NAME = ""