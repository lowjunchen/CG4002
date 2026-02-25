import wave
import numpy as np
import math

SAMPLE_RATE = 16000
WINDOW_SECONDS = 1.0
WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SECONDS)
FRAME_LENGTH = 400
FRAME_STEP = 160
FFT_SIZE = 512
NUM_MEL_FILTERS = 40
NUM_MFCC = 13
LOW_FREQ = 20
HIGH_FREQ = 4000
PRE_EMPHASIS = 0.97

def load_wav(filename):
    """
    Open the binary file and read data in binary mode
    
    :param filename: path to the .wav file
    :return: normalized audio signal as a numpy array
    """
    with wave.open(filename, 'rb') as wf: 
        assert wf.getnchannels() == 1
        assert wf.getframerate() == SAMPLE_RATE

        samples = wf.readframes(wf.getnframes())
        signal = np.frombuffer(samples, dtype=np.int16).astype(np.float32)
        return signal
    
def pre_emphasis(signal):
    """
    Apply pre-emphasis filter to the signal to boost 
    high frequencies and improve feature extraction
    
    :param signal: input audio signal
    :return: pre-emphasised signal
    """
    emphasised = np.empty_like(signal)
    emphasised[0] = signal[0]
    emphasised[1:] = signal[1:] - PRE_EMPHASIS * signal[:-1]
    return emphasised

def framing(signal):
    """
    Create frames from the input signal by slicing it into overlapping segments.
    Assuming a sample rate of 16kHz, a frame length of 25ms (400 samples) and a 
    frame step of 10ms (160 samples).
    
    :param signal: input audio signal
    :return: 2D array of frames (num_frames x frame_length)
    """
    num_frames = 1 + int((len(signal) - FRAME_LENGTH) / FRAME_STEP)

    indices = (
        np.tile(np.arange(FRAME_LENGTH), (num_frames, 1)) +
        np.tile(np.arange(0, num_frames * FRAME_STEP, FRAME_STEP), (FRAME_LENGTH, 1)).T
    )

    return signal[indices]

def windowing(frames):
    """
    Apply Hamming window to each frame to minimize spectral leakage before FFT.
    
    :param frames: 2D array of frames (num_frames x frame_length)
    :return: windowed frames
    """
    hamming = 0.54 - 0.46 * np.cos(
        2 * np.pi * np.arange(FRAME_LENGTH) / (FRAME_LENGTH - 1)
    )
    return frames * hamming

def power_spectrum(frames):
    """
    Compute the power spectrum of each frame using FFT. 
    
    :param frames: 2D array of frames (num_frames x frame_length)
    :return: 2D array of power spectra (num_frames x (FFT_SIZE // 2 + 1))
    """
    fft = np.fft.rfft(frames, FFT_SIZE)
    power = (np.abs(fft) ** 2) / FFT_SIZE
    return power


def hz_to_mel(hz):
    """
    Convert frequency in Hertz to Mel scale.
    
    :param hz: frequency in Hertz
    :return: frequency in Mel scale
    """
    return 2595 * np.log10(1 + hz / 700.0)


def mel_to_hz(mel):
    """
    Convert frequency in Mel scale to Hertz.
    
    :param mel: frequency in Mel scale
    :return: frequency in Hertz
    """
    return 700 * (10 ** (mel / 2595.0) - 1)


def mel_filterbank():
    """
    Create a Mel filterbank matrix to map the power spectrum to the Mel scale.

    :return: Mel filterbank matrix
    """
    low_mel = hz_to_mel(LOW_FREQ)
    high_mel = hz_to_mel(HIGH_FREQ)

    mel_points = np.linspace(low_mel, high_mel, NUM_MEL_FILTERS + 2)
    hz_points = mel_to_hz(mel_points)

    bins = np.floor((FFT_SIZE + 1) * hz_points / SAMPLE_RATE).astype(int)

    filters = np.zeros((NUM_MEL_FILTERS, FFT_SIZE // 2 + 1))

    for m in range(1, NUM_MEL_FILTERS + 1):
        f_left, f_center, f_right = bins[m - 1], bins[m], bins[m + 1]

        for k in range(f_left, f_center):
            filters[m - 1, k] = (k - f_left) / (f_center - f_left)

        for k in range(f_center, f_right):
            filters[m - 1, k] = (f_right - k) / (f_right - f_center)

    return filters

def dct_matrix():
    """
    Create a DCT (Discrete Cosine Transform) matrix to convert log Mel energies to MFCCs.

    :return: DCT matrix
    """
    N = NUM_MEL_FILTERS
    K = NUM_MFCC

    dct = np.zeros((K, N))
    for k in range(K):
        for n in range(N):
            dct[k, n] = math.cos(math.pi * k * (2*n + 1) / (2*N))

    return dct

def compute_mfcc_wav(filename):
    """
    Compute MFCC features from a .wav file.

    :param filename: Description of the .wav file to process
    :return: 2D array of MFCC features (num_frames x NUM_MFCC)
    """

    signal = load_wav(filename)
    audio_np = signal.astype(np.float32) / 32768.0

    #Pad the sample audio to 1 second (16000 samples) if it's shorter, or truncate if it's longer
    if audio_np.shape[0] < WINDOW_SAMPLES:
        audio_np = np.pad(audio_np, (0, WINDOW_SAMPLES - audio_np.shape[0]))
    else:
        audio_np = audio_np[:WINDOW_SAMPLES]

    emphasised_signal = pre_emphasis(audio_np)

    frames = framing(emphasised_signal)
    frames = windowing(frames)

    power = power_spectrum(frames)

    mel_filters = mel_filterbank()
    mel_energy = np.dot(power, mel_filters.T)

    mel_energy = np.log(mel_energy + 1e-10)

    dct = dct_matrix()
    mfcc = np.dot(mel_energy, dct.T)

    return mfcc

def compute_mfcc_np(signal):
    """
    Compute MFCC features from a np array.

    :param signal: input audio signal as a numpy array
    :return: 2D array of MFCC features (num_frames x NUM_MFCC)
    """
    audio_np = signal.astype(np.float32) / 32768.0

    #Pad the sample audio to 1 second (16000 samples) if it's shorter, or truncate if it's longer
    if audio_np.shape[0] < WINDOW_SAMPLES:
        audio_np = np.pad(audio_np, (0, WINDOW_SAMPLES - audio_np.shape[0]))
    else:
        audio_np = audio_np[:WINDOW_SAMPLES]

    emphasised_signal = pre_emphasis(audio_np)

    frames = framing(emphasised_signal)
    frames = windowing(frames)

    power = power_spectrum(frames)

    mel_filters = mel_filterbank()
    mel_energy = np.dot(power, mel_filters.T)

    mel_energy = np.log(mel_energy + 1e-10)

    dct = dct_matrix()
    mfcc = np.dot(mel_energy, dct.T)

    return mfcc

""" #Test the code with a sample .wav file from the speech commands dataset.
if __name__ == "__main__":
    audio, label_idx, label_name = fetch_one_tfds_sample(split="test")
    mfcc =  compute_mfcc_np(audio)
    print(f"MFCC shape: {mfcc.shape}, Label: {label_name}")
    np.set_printoptions(precision=4, suppress=True, linewidth=160) 
    print("MFCC features for the first frame:")
    print(mfcc) """