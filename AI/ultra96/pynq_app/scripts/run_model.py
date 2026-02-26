import os
import json 
import numpy as np
import time

from pynq import PL

from pynq_app.src.overlay_loader import load_overlay
from pynq_app.src.dma_control import dma_transfer_axis32
from pynq_app.src.config import AXIS_W, IN_LEN, OUT_LEN

from pynq_app.utils.postprocess_data import logits_to_label
from pynq_app.utils.preprocess_data import compute_mfcc_wav

def main():
    os.makedirs("data/output", exist_ok=True)

    in_wav = "data/input/go.wav"
    if not os.path.exists(in_wav):
        raise FileNotFoundError(f"Missing input wav: {in_wav}")

    PL.reset()

    # 1) Preprocess data to MFCC
    t0 = time.time()

    mfcc_flat = compute_mfcc_wav(in_wav).reshape(-1).astype(np.float32)
    mfcc_flat_f32 = mfcc_flat.view(np.uint32)
    print(f"MFCC words computed: {mfcc_flat_f32.size}, expected IN_LEN: {IN_LEN}")
    if mfcc_flat_f32.size != IN_LEN:
        raise ValueError(f"Input length mismatch: got {mfcc_flat_f32.size} words, expected {IN_LEN}")

    print("Actual input length is: ",  len(mfcc_flat_f32))
    assert len(mfcc_flat_f32) == IN_LEN
    

    # 2) Load overlay + DMA
    t1 = time.time()

    ol, dma = load_overlay()

    # 3) DMA Inference
    t2 = time.time()

    '''
    if accel is not None:
        start(accel)
    '''
        
    logits = dma_transfer_axis32(
        dma=dma,
        in_np=mfcc_flat_f32,
        out_len=OUT_LEN,
    )
    print(f"DMA output words received: {logits.size}, expected OUT_LEN: {OUT_LEN}")
    if logits.size != OUT_LEN:
        raise ValueError(f"Output length mismatch: got {logits.size} words, expected {OUT_LEN}")
    
    logits_f32 = logits.view(np.float32)

    # 4) Unpack logits + label    
    t3 = time.time()
    
    pred_idx, pred_label = logits_to_label(logits_f32)

    # 5）Save results
    result = {
        "input_file": in_wav,
        "axis_w": AXIS_W,
        "in_len_words": int(IN_LEN),
        "out_len_words": int(OUT_LEN),
        "logits": logits.astype(float).tolist(),
        "predicted_index": int(pred_idx),
        "predicted_label": pred_label,
        "timing_ms": {
            "preprocess": (t1 - t0) * 1000.0,
            "overlay_load_and_dma": (t3 - t2) * 1000.0,
            "total": (t3 - t0) * 1000.0,
        },
    }

    with open("data/output/result.json", "w") as f:
        json.dump(result, f, indent=2)

    with open("data/output/result.txt", "w") as f:
        f.write(f"File: {in_wav}\n")
        f.write(f"Pred: {pred_label} (idx={pred_idx})\n")
        f.write(f"Logits: {logits}\n")

    print(f"Predicted: {pred_label} (idx={pred_idx})")
    print("Wrote: data/output/result.json and data/output/result.txt")    

if __name__ == "__main__":
    main()
