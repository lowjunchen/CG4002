import numpy as np

# Existing labels
TARGET_COMMANDS = [
    'go',
    'on', 
    'stop', 
    'up', 
    'down', 
    '_silence_', 
    '_unknown_'
]

def logits_to_label(logits, verbose=True):
    """
    Convert model output logits to a human-readable label.

    :param logits: 1D array of raw model outputs (logits)
    :return: predicted label as a string
    """
    logits = np.asarray(logits, dtype=np.float32)
    
    predicted_idx = int(np.argmax(logits))
    
    if predicted_idx >= len(TARGET_COMMANDS):
        label = "_unknown_"
    else:
        label = TARGET_COMMANDS[predicted_idx]

    if verbose:
        print("=== Postprocess Result ===")
        print("Logits:")
        for i, (lbl, val) in enumerate(zip(TARGET_COMMANDS, logits)):
            print(f"  [{i}] {lbl:10s}: {val:.6f}")
        print("--------------------------")
        print(f"Predicted index : {predicted_idx}")
        print(f"Predicted label : {label}")
        print("==========================")

    return predicted_idx, label