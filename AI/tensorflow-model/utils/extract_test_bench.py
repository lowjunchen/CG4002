import os
import numpy as np
import tensorflow as tf
from data.extract_data import load_custom_dataset

"""
Script to extract data to be used in the HLS test bench for the CNN KWS model. This includes:
- Input MFCCs and corresponding labels for a few test samples
- Expected output logits for those test samples
"""

MODEL_PATH = "cnn_kws_model"
OUTPUT_DIR = "hls_tb_io"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def extract_test_bench_data(model_path=MODEL_PATH, output_dir=OUTPUT_DIR, num_samples=1):
    """
    Extract test bench data from the trained KWS model.
    """
    ensure_dir(output_dir)
    model = tf.keras.models.load_model(model_path)

    ds = load_custom_dataset(batch_size=1, augment=False)

    for mfcc, label in ds.take(num_samples):
        x = mfcc.numpy() 
        y = label.numpy()

    #remove batch dimension
    if len(x.shape) == 4:
        mfcc_2d = x[0]
    
    if len(mfcc_2d.shape) == 3 and mfcc_2d.shape[-1] == 1:
        mfcc_2d = mfcc_2d[:, :, 0]
    
    logits = model(x, training=False).numpy()[0]  # Get the logits for the single sample
    print("Label:", y)
    print("Logits:", logits)

    mfcc_flat = mfcc_2d.reshape(-1).astype(np.float32)

    # Save MFCC
    np.savetxt(
        os.path.join(OUTPUT_DIR, "mfcc_in_0.csv"),
        mfcc_flat,
        delimiter=",",
        fmt="%.10e"
    )

    # Save logits
    np.savetxt(
        os.path.join(OUTPUT_DIR, "logits_out_0.csv"),
        logits,
        delimiter=",",
        fmt="%.10e"
    )

    print("\nExport complete.")
    print("Files written:")
    print("  mfcc_in_0.csv")
    print("  logits_out_0.csv")


if __name__ == "__main__":
    extract_test_bench_data(num_samples=1)