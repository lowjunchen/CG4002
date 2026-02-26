import numpy as np
import tensorflow as tf
from utils.convert_to_mfcc import compute_mfcc_np

"""
Script to extract input/output shapes, weight shapes, and activation ranges from the trained KWS model.
"""

def extract_IO_shapes(model_path="cnn_kws_model"):
    """
    Load the trained KWS model and extract input/output shapes, weight shapes, and activation ranges.

    :param model_path: Path to the saved KWS model (default: "cnn_kws_model")
    """
    model = tf.keras.models.load_model(model_path)

    print("Model input shape :", model.input_shape)   # (None, H, W, C)
    print("Model output shape:", model.output_shape)  # (None, num_classes)

    # Per-layer output shapes
    for i, layer in enumerate(model.layers):
        print(f"{i:02d} {layer.name:25s} {layer.__class__.__name__:20s} -> {layer.output_shape}")
    
    #Verify the shape of weights at each layer
    weights = model.get_weights()
    for i, w in enumerate(weights):
        print(i, w.shape)

    for layer in model.layers:
        if layer.weights:
            print(layer.name, layer.__class__.__name__)
            for v in layer.weights:
                print("  ", v.name, v.shape)
    
    # Pick a dummy input, verify the range of logits at the output layer
    x = np.random.randn(1,98,13,1).astype(np.float32)
    logits = model(x).numpy()

    print("logits min/max:", logits.min(), logits.max())
    print("sum(exp(logits)):", np.sum(np.exp(logits)))

    # Verify min and max values at each layer to understand activation ranges
    layer_outputs = [layer.output for layer in model.layers]
    probe = tf.keras.Model(inputs=model.input, outputs=layer_outputs)

    x = np.random.randn(1,98,13,1).astype(np.float32)
    outs = probe(x)

    for layer, out in zip(model.layers, outs):
        out_np = out.numpy()
        print(f"{layer.name:25s} shape={out_np.shape} min={out_np.min():.4f} max={out_np.max():.4f}")

def extract_mfcc_shapes():
    """
    Generate dummy audio data and compute MFCCs to verify the expected shape.
    """
    dummy = (np.random.randn(16000) * 1000).astype(np.int16)  # Use dummy audio data to test MFCC extraction
    mfcc = compute_mfcc_np(dummy)

    print("MFCC shape:", mfcc.shape)  # expect (98, 13)

if __name__ == "__main__":
    extract_IO_shapes()
    extract_mfcc_shapes()