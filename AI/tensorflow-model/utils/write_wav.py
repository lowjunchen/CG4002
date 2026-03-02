import os
import wave
import numpy as np

def write_wav_int16(path, audio_in16, sample_rate=16000):
    """
    Write a numpy array of int16 audio samples to a .wav file.
    
    :param path: output file path (e.g., 'output.wav')
    :param audio_in16: numpy array of int16 audio samples
    :param sample_rate: sample rate in Hz (default: 16000)
    """
    audio_int16 = np.asarray(audio_in16, dtype=np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16 bits = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())