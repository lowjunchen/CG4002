import json
import time
import numpy as np


class VoiceDataCollector:
    """
    Collects voice packets from MQTT and tracks timing.
    """

    def __init__(self, audio_buffer):
        self.audio_buffer = audio_buffer
        self.pkt_counter = 0
        self.start_time = 0

    def voice_data_handler(self, payload):
        if self.pkt_counter == 0:
            self.start_time = time.time()

        in_pkt = np.frombuffer(payload, dtype=np.int16)
        self.audio_buffer.append(in_pkt)
        self.pkt_counter += 1
        print(f"Packet {self.pkt_counter} received ({len(in_pkt)} samples)")

    def is_ready(self, timeout_sec=2, max_packets=3):
        if self.pkt_counter == 0:
            return False
        return (time.time() - self.start_time > timeout_sec) or (self.pkt_counter >= max_packets)

    def reset(self):
        self.pkt_counter = 0
        self.start_time = 0
        self.audio_buffer.clear()