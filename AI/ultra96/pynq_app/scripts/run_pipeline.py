import os
import json
import time
import numpy as np

from pynq import PL
from pathlib import Path

from pynq_app.src.overlay_loader import load_overlay
from pynq_app.src.dma_control import dma_transfer_axis32
from pynq_app.src.config import IN_LEN, OUT_LEN
from pynq_app.src.power_manager import apply_profile
from pynq_app.src.config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS
from pynq_app.src.mqtt_client import SecureMQTTClient
from AI.ultra96.pynq_app.src.audio_buffer import AudioBuffer
from pynq_app.src.mqtt_handlers import VoiceDataCollector
from pynq_app.src.inference import run_inference_on_windows

SAMPLE_RATE = 8000
WINDOW_SIZE = SAMPLE_RATE * 1       # 1 second window
HOP_SIZE = SAMPLE_RATE // 2         # 50% overlap in inference window

def main():
    # Runtime power profile before active work.
    apply_profile("performance")

    PL.reset()
    ol, dma = load_overlay()
    print("Overlay and DMA loaded.")

    audio_buf = AudioBuffer(window_size=WINDOW_SIZE, hop_size=HOP_SIZE)
    collector = VoiceDataCollector(audio_buf)

    mqtt_client = SecureMQTTClient(
        username=MQTT_USER,
        password=MQTT_PASS,
        host=MQTT_HOST,
        port=MQTT_PORT,
        client_id="ultra96",
        cert_dir=Path(__file__).resolve().parent.parent / "certs",
    )
    mqtt_client.connect()
    mqtt_client.register_handler("esp32/voice_data", collector.voice_data_handler, qos=1) #Topic title from esp
    print("MQTT connected, waiting for packets...")

    try:
        while True:
            if collector.is_ready():
                windows = audio_buf.get_windows()

                if len(windows) == 0:
                    out_pkt = {"status": "FAILED", "info": "Insufficient audio data"} #Troubleshoot message
                    print("No complete windows available.")
                else:
                    print(f"Running inference on {len(windows)} overlapping windows...")
                    best_label, _ = run_inference_on_windows(windows, dma)
                    out_pkt = {"status": "SUCCESS", "result": best_label} #Inference message

                collector.reset()
                json_pkt = json.dumps(out_pkt)
                mqtt_client.publish("ultra96/voice_result", json_pkt) #Topic title for Ultra96
                print(f"Published: {json_pkt}")

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Shut down by user.")
        apply_profile("powersave")
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()