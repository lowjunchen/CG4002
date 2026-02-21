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

def write_h_header(filepath, var_name, array, dtype="float"):
    """
    Initialize a C header file with a static const array definition.

    :param filepath: Path to the output .h file
    :param var_name: Name of the C variable to define
    :param array: Numpy array to write (can be 4D or any shape)
    :param dtype: C data type to use (default: "float")
    """
    flat = array.flatten()

    with open(filepath, "w") as f:
        f.write("#pragma once\n\n")
        f.write(f"static const {dtype} {var_name}[{len(flat)}] = {{\n")

        # Write values in scientific notation, 8 per line
        for i, val in enumerate(flat):
            f.write(f"{float(val):.10e},")
            if (i + 1) % 8 == 0:
                f.write("\n")

        f.write("\n};\n")


def export_layer(layer, export_dir):
    weights = layer.get_weights()
    if not weights:
        return

    print(f"\nExporting layer: {layer.name} ({layer.__class__.__name__})")

    #Exporting weight and bias for Conv layers and Dense layers
    if isinstance(layer, tf.keras.layers.Conv2D) or isinstance(layer, tf.keras.layers.Dense):
        kernel, bias = weights

        print("  Kernel shape:", kernel.shape)
        print("  Bias shape  :", bias.shape)

        write_h_header(
            os.path.join(export_dir, f"{layer.name}_w.h"),
            f"{layer.name}_w",
            kernel
        )

        write_h_header(
            os.path.join(export_dir, f"{layer.name}_b.h"),
            f"{layer.name}_b",
            bias
        )

        # For CSV export, flatten the kernel to 1D for easier parsing in C/C++
        if EXPORT_CSV:
            np.savetxt(
                os.path.join(export_dir, f"{layer.name}_w.csv"),
                kernel.flatten(),
                delimiter=","
            )
            np.savetxt(
                os.path.join(export_dir, f"{layer.name}_b.csv"),
                bias,
                delimiter=","
            )
        
        # For NPY export, save the kernel and bias in their original shapes for potential use in Python or other tools
        if EXPORT_NPY:
            np.save(os.path.join(export_dir, f"{layer.name}_w.npy"), kernel)
            np.save(os.path.join(export_dir, f"{layer.name}_b.npy"), bias)

def main():
    ensure_dir(EXPORT_DIR)

    model = tf.keras.models.load_model(MODEL_PATH)

    print("Model summary:")
    model.summary()

    # Export weights for each layer
    for layer in model.layers:
        export_layer(layer, EXPORT_DIR)

    print("\nAll weights exported to:", EXPORT_DIR)


if __name__ == "__main__":
    main()