import time
import numpy as np


class VoiceDataCollector:
    """
    Collects voice packets from MQTT and tracks timing.
    """

    def __init__(self, audio_buffer):
        self.audio_buffer = audio_buffer
        self.batch_pkt_counter = 0
        self.batch_sample_counter = 0

    def voice_data_handler(self, client_or_payload, msg=None):
        payload = client_or_payload if msg is None else msg.payload
        raw = np.frombuffer(payload, dtype=np.uint8)
        in_pkt = (raw.astype(np.int16) - 128) * 256
        self.audio_buffer.append(in_pkt)
        self.batch_pkt_counter += 1
        self.batch_sample_counter += len(in_pkt)
        print(
            f"Packet {self.batch_pkt_counter} received "
            f"({len(in_pkt)} samples, buffered={self.audio_buffer.sample_count()})"
        )

    def is_ready(self, min_samples):
        return self.audio_buffer.sample_count() >= min_samples

    def reset(self):
        # Keep the overlap tail in AudioBuffer; only reset batch counters.
        self.batch_pkt_counter = 0
        self.batch_sample_counter = 0
