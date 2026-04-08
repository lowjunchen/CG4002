import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

from data.extract_data import fetch_speech_data_in_mfcc
from utils.convert_to_mfcc import chunk_wav_to_mfccs

MODEL_PATH = 'cnn_kws_model'
BATCH_SIZE = 64

TARGET_COMMANDS = ['start', 'end', 'play', 'pause', 'faster', 'slower', 'unknown']


def evaluate_wav(wav_path, model_path=MODEL_PATH, overlap=0.5):
    """
    Evaluate a single .wav file by chunking it into 1-second segments
    with the given overlap and running inference on each segment.

    :param wav_path: path to the .wav file (mono, 8kHz)
    :param model_path: path to the saved Keras model
    :param overlap: overlap fraction between segments (default 0.5)
    :return: list of (segment_index, predicted_label, confidence) tuples
    """
    model = tf.keras.models.load_model(model_path)
    mfccs = chunk_wav_to_mfccs(wav_path, overlap=overlap)

    results = []
    for i, mfcc in enumerate(mfccs):
        x = np.expand_dims(mfcc, axis=-1)  # (98, 13, 1)
        x = np.expand_dims(x, axis=0)      # (1, 98, 13, 1)

        logits = model(x, training=False)
        probs = tf.nn.softmax(logits, axis=1).numpy()[0]
        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])

        results.append((i, TARGET_COMMANDS[pred_idx], confidence))
        print(f'Segment {i}: {TARGET_COMMANDS[pred_idx]} ({confidence:.2%})')

    return results


def evaluate_model(model_path = MODEL_PATH):
    model = tf.keras.models.load_model(model_path)

    _, test_ds = fetch_speech_data_in_mfcc(batch_size=BATCH_SIZE, training=False)

    y_true_batches = []
    y_pred_batches = []

    for x_batch, y_batch in test_ds:
        logits = model(x_batch, training=False)
        pred = tf.argmax(logits, axis=1, output_type=tf.int64) # Extract label of the highest logit as prediction

        y_true_batches.append(tf.cast(y_batch, tf.int64).numpy())
        y_pred_batches.append(pred.numpy())

    y_true = np.concatenate(y_true_batches)
    y_pred = np.concatenate(y_pred_batches)

    accuracy = float(np.mean(y_true == y_pred))
    
    # Draw a confusion matrix to examine the wrong results
    cm = tf.math.confusion_matrix(
        y_true,
        y_pred,
        num_classes=len(TARGET_COMMANDS),
        dtype=tf.int32,
    ).numpy()

    return accuracy, cm


def print_confusion_matrix(cm, class_names):
    header = 'true\\pred'.ljust(14) + ' '.join([name.rjust(10) for name in class_names])
    print(header)
    for i, row in enumerate(cm):
        row_str = class_names[i].ljust(14) + ' '.join([str(v).rjust(10) for v in row])
        print(row_str)


def evaluate_wav_dir(wav_dir, model_path=MODEL_PATH, overlap=0.5, plot_cm=False):
    """
    Evaluate all .wav files in a directory organised by label subdirectories,
    predicting a single label per file (highest average confidence across segments).

    :param wav_dir: path to directory containing label subdirectories with .wav files
    :param model_path: path to the saved Keras model
    :param overlap: overlap fraction between segments (default 0.5)
    :param plot_cm: if True, plot a confusion matrix after evaluation
    """
    import os
    model = tf.keras.models.load_model(model_path)

    col_w = [30, 12, 12, 12]
    header = f"{'File':<{col_w[0]}} {'True':<{col_w[1]}} {'Prediction':<{col_w[2]}} {'Confidence':>{col_w[3]}}"
    sep = '-' * (sum(col_w) + 3)
    print(header)
    print(sep)

    y_true = []
    y_pred = []

    for label_dir in sorted(os.listdir(wav_dir)):
        label_path = os.path.join(wav_dir, label_dir)
        if not os.path.isdir(label_path):
            continue
        true_label = label_dir

        wav_files = sorted([f for f in os.listdir(label_path) if f.lower().endswith('.wav')])
        for fname in wav_files:
            path = os.path.join(label_path, fname)
            mfccs = chunk_wav_to_mfccs(path, overlap=overlap)

            all_probs = []
            for mfcc in mfccs:
                x = np.expand_dims(mfcc, axis=-1)
                x = np.expand_dims(x, axis=0)
                logits = model(x, training=False)
                probs = tf.nn.softmax(logits, axis=1).numpy()[0]
                all_probs.append(probs)

            avg_probs = np.mean(all_probs, axis=0)
            pred_idx = int(np.argmax(avg_probs))
            confidence = float(avg_probs[pred_idx])
            pred_label = TARGET_COMMANDS[pred_idx]

            y_true.append(true_label)
            y_pred.append(pred_label)

            match = '' if true_label == pred_label else ' <-- WRONG'
            print(f"{fname:<{col_w[0]}} {true_label:<{col_w[1]}} {pred_label:<{col_w[2]}} {confidence:>{col_w[3]-1}.2%}{match}")

    accuracy = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true) if y_true else 0
    print(sep)
    print(f"Accuracy: {accuracy:.2%} ({sum(t == p for t, p in zip(y_true, y_pred))}/{len(y_true)})")

    if plot_cm and y_true:
        cm = tf.math.confusion_matrix(
            [TARGET_COMMANDS.index(t) for t in y_true],
            [TARGET_COMMANDS.index(p) for p in y_pred],
            num_classes=len(TARGET_COMMANDS),
            dtype=tf.int32,
        ).numpy()
        print_confusion_matrix(cm, TARGET_COMMANDS)


def main():
    #accuracy, cm = evaluate_model()

    #print(f'Test accuracy: {accuracy * 100.0:.2f}%')
    #print('Confusion matrix (rows=true, cols=pred):')
    #print_confusion_matrix(cm, TARGET_COMMANDS)
    wav_dir = r"E:\AI-for-CG4002\AI\tensorflow-model\data\test_wav_samples"
    evaluate_wav_dir(wav_dir, plot_cm=True)

if __name__ == '__main__':
    main()
