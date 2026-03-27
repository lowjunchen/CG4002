import os
import numpy as np
import tensorflow as tf


MODEL_PATH = "cnn_kws_model"
EXPORT_DIR = "hls_weights"
EXPORT_CSV = False
EXPORT_NPY = False


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def write_h_header(filepath, var_name, array, dtype="data_t"):
    """
    Initialize a C header file with a static const array definition.

    :param filepath: Path to the output .h file
    :param var_name: Name of the C variable to define
    :param array: Numpy array to write (can be 4D or any shape)
    :param dtype: C data type to use (default: "float")
    """
    flat = array.flatten()

    with open(filepath, "w") as f:
        f.write("#pragma once\n")
        f.write("#include \"kws_hls.h\"\n\n") # Include header to define fixed-point datatype data_t
        f.write(f"static const {dtype} {var_name}[{len(flat)}] = {{\n")

        # Write values in scientific notation, 8 per line
        for i, val in enumerate(flat):
            f.write(f"{float(val):.10e},")
            if (i + 1) % 8 == 0:
                f.write("\n")

        f.write("\n};\n")


def fuse_conv_bn(kernel, bias, gamma, beta, moving_mean, moving_variance, eps=1e-3):
    """
    Fold BatchNormalization parameters into Conv2D kernel and bias.
    """
    scale   = gamma / np.sqrt(moving_variance + eps)  
    w_fused = kernel * scale                         
    b_fused = (bias - moving_mean) * scale + beta       
    return w_fused, b_fused


def export_conv_weights(layer_name, kernel, bias, export_dir):
    print(f"  Kernel shape: {kernel.shape}")
    print(f"  Bias shape  : {bias.shape}")

    write_h_header(os.path.join(export_dir, f"{layer_name}_w.h"), f"{layer_name}_w", kernel)
    write_h_header(os.path.join(export_dir, f"{layer_name}_b.h"), f"{layer_name}_b", bias)

    if EXPORT_CSV:
        np.savetxt(os.path.join(export_dir, f"{layer_name}_w.csv"), kernel.flatten(), delimiter=",")
        np.savetxt(os.path.join(export_dir, f"{layer_name}_b.csv"), bias, delimiter=",")

    if EXPORT_NPY:
        np.save(os.path.join(export_dir, f"{layer_name}_w.npy"), kernel)
        np.save(os.path.join(export_dir, f"{layer_name}_b.npy"), bias)


def main():
    ensure_dir(EXPORT_DIR)

    model = tf.keras.models.load_model(MODEL_PATH)

    print("Model summary:")
    model.summary()

    layers = model.layers
    i = 0
    while i < len(layers):
        layer = layers[i]

        if isinstance(layer, tf.keras.layers.Conv2D):
            kernel, bias = layer.get_weights()

            # If the next layer is BatchNorm, fold it into the conv weights
            if i + 1 < len(layers) and isinstance(layers[i + 1], tf.keras.layers.BatchNormalization):
                bn = layers[i + 1]
                gamma, beta, moving_mean, moving_variance = bn.get_weights()
                print(f"\nExporting layer: {layer.name} ({layer.__class__.__name__}) + {bn.name} (BatchNormalization) [fused]")
                kernel, bias = fuse_conv_bn(kernel, bias, gamma, beta, moving_mean, moving_variance)
                i += 2  # consume both Conv and BN
            else:
                print(f"\nExporting layer: {layer.name} ({layer.__class__.__name__})")
                i += 1

            export_conv_weights(layer.name, kernel, bias, EXPORT_DIR)

        elif isinstance(layer, tf.keras.layers.Dense):
            kernel, bias = layer.get_weights()
            print(f"\nExporting layer: {layer.name} ({layer.__class__.__name__})")
            export_conv_weights(layer.name, kernel, bias, EXPORT_DIR)
            i += 1

        else:
            i += 1

    print("\nAll weights exported to:", EXPORT_DIR)


if __name__ == "__main__":
    main()