import os
import wave
import numpy as np
from scipy.signal import decimate

OUTPUT_SAMPLE_RATE = 8000

def write_wav_int16(path, audio_in16, input_sample_rate=16000):
    """
    Write a numpy array of int16 audio samples to a .wav file.
    If the input sample rate is higher than 8000 Hz, the audio is
    downsampled to 8000 Hz before writing.

    :param path: output file path (e.g., 'output.wav')
    :param audio_in16: numpy array of int16 audio samples
    :param input_sample_rate: sample rate of the input audio in Hz (default: 16000)
    """
    audio_int16 = np.asarray(audio_in16, dtype=np.int16)

    if input_sample_rate > OUTPUT_SAMPLE_RATE:
        factor = input_sample_rate // OUTPUT_SAMPLE_RATE
        audio_int16 = decimate(audio_int16, factor).astype(np.int16)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16 bits = 2 bytes
        wf.setframerate(OUTPUT_SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())