import os
import json
import argparse
import time

from pynq import PL

from pynq_app.src.overlay_loader import load_overlay
from pynq_app.src.config import AXIS_W, IN_LEN, OUT_LEN
from pynq_app.src.power_manager import apply_profile
from pynq_app.src.inference import run_inference_on_windows

from pynq_app.utils.preprocess_data import load_wav_windows

def main(input_path, pre_profile="performance", post_profile="powersave"):
    os.makedirs("data/output", exist_ok=True)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Missing input wav: {input_path}")

    # Runtime power profile before active work.
    apply_profile(pre_profile)

    PL.reset()

    # 1) Load overlay + DMA
    ol, dma = load_overlay()

    # 2) Load and chunk wav into 1-second windows
    t0 = time.time()

    windows = load_wav_windows(input_path)
    print(f"Loaded {len(windows)} window(s) from {input_path}")

    # 3) Run inference across all windows
    t1 = time.time()

    best_label, best_confidence = run_inference_on_windows(windows, dma)

    t2 = time.time()

    # 4) Save results
    result = {
        "input_file": input_path,
        "axis_w": AXIS_W,
        "in_len_words": int(IN_LEN),
        "out_len_words": int(OUT_LEN),
        "num_windows": len(windows),
        "predicted_label": best_label,
        "best_confidence": best_confidence,
        "timing_ms": {
            "preprocess": (t1 - t0) * 1000.0,
            "inference": (t2 - t1) * 1000.0,
            "total": (t2 - t0) * 1000.0,
        },
    }

    with open("data/output/result.json", "w") as f:
        json.dump(result, f, indent=2)

    with open("data/output/result.txt", "w") as f:
        f.write(f"File: {input_path}\n")
        f.write(f"Pred: {best_label} (confidence={best_confidence:.4f})\n")
        f.write(f"Windows: {len(windows)}\n")

    print(f"Predicted: {best_label} (confidence={best_confidence:.4f})")
    print(f"Inference time (ms): {(t2 - t1) * 1000.0:.2f}")
    print("Wrote: data/output/result.json and data/output/result.txt")

    # Runtime power profile after active work.
    apply_profile(post_profile)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PYNQ CNN inference")
    parser.add_argument(
        "--input_path",
        "-i",
        required=True,
        help="Path to input WAV file",
    )
    parser.add_argument(
        "--pre_profile",
        choices=["performance", "powersave"],
        default="performance",
        help="Power profile to apply before inference",
    )
    parser.add_argument(
        "--post_profile",
        choices=["performance", "powersave"],
        default="powersave",
        help="Power profile to apply after inference",
    )
    args = parser.parse_args()

    main(
        input_path=args.input_path,
        pre_profile=args.pre_profile,
        post_profile=args.post_profile,
    )
