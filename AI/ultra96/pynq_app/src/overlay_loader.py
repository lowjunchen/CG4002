from pynq import Overlay
from .config import OVERLAY_BIT, DMA_NAME, ACCEL_NAME

def load_overlay():
    """Loads the overlay and returns the accelerator and DMA objects."""
    overlay = Overlay(OVERLAY_BIT)
    overlay.download()
    dma = overlay.__getattr__(DMA_NAME)
    #accel = overlay.__getattr__(ACCEL_NAME)
    return overlay, dma