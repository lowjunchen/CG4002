import numpy as np

from pynq_app.src.dma_control import dma_transfer_axis32
from pynq_app.src.config import IN_LEN, OUT_LEN
from pynq_app.src.dma_control import dma_transfer_axis32

from pynq_app.utils.postprocess_data import logits_to_label
from pynq_app.utils.preprocess_data import compute_mfcc_np

def classify_audio(waveform, dma):
    """
    Takes a raw waveform and computes MFCC.
    Runs DMA inference, returns labels.
    """
    mfcc_flat = compute_mfcc_np(waveform).reshape(-1).astype(np.float32)
    mfcc_flat_f32 = mfcc_flat.view(np.uint32)

    if mfcc_flat_f32.size != IN_LEN:
        print(f"Input length mismatch: got {mfcc_flat_f32.size}, expected {IN_LEN}")
        return "_unknown_", -float("inf")

    logits = dma_transfer_axis32(dma=dma, in_np=mfcc_flat_f32, out_len=OUT_LEN)
    logits_f32 = logits.view(np.float32)

    pred_idx, pred_label = logits_to_label(logits_f32)
    confidence = float(logits_f32[pred_idx])

    return pred_label, confidence

def run_inference_on_windows(windows, dma):
    """
    Run inference on each overlapping window.
    Return the label with the highest confidence
    """
    best_label = "_unknown_"
    best_confidence = -float("inf")

    for i, window in enumerate(windows):
        label, confidence = classify_audio(window, dma)
        print(f"  Window {i}: {label} (confidence={confidence:.4f})")
        if confidence > best_confidence:
            best_confidence = confidence
            best_label = label

    return best_label, best_confidence
