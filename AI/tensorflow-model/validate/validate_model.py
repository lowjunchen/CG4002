import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

from data.extract_data import fetch_speech_data_in_mfcc
from utils.convert_to_mfcc import chunk_wav_to_mfccs

MODEL_PATH = 'cnn_kws_model'
BATCH_SIZE = 64

TARGET_COMMANDS = ['go', 'on', 'stop', 'up', 'down', '_silence_', '_unknown_']


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


def main():
    #accuracy, cm = evaluate_model()

    #print(f'Test accuracy: {accuracy * 100.0:.2f}%')
    #print('Confusion matrix (rows=true, cols=pred):')
    #print_confusion_matrix(cm, TARGET_COMMANDS)
    evaluate_wav(r"E:\AI-for-CG4002\AI\tensorflow-model\data\wav_samples\audio_unknown.wav")

if __name__ == '__main__':
    main()
