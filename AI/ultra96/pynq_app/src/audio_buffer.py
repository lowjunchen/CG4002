import numpy as np

class AudioBuffer:
    """
    Rolling buffer that yields overlapping inference windows.
    Uses overlap to prevent a single command being chunked in
    two separate windows
    """

    def __init__(self, window_size, hop_size):
        self.window_size = window_size
        self.hop_size = hop_size
        self.buffer = np.array([], dtype=np.int16)

    def append(self, chunk):
        self.buffer = np.append(self.buffer, chunk)

    def get_windows(self):
        windows = []
        offset = 0
        while offset + self.window_size <= len(self.buffer):
            windows.append(self.buffer[offset : offset + self.window_size].copy())
            offset += self.hop_size

        # Keep unprocessed tail for next batch
        if offset > 0:
            self.buffer = self.buffer[offset:]

        return windows

    def clear(self):
        self.buffer = np.array([], dtype=np.int16)
