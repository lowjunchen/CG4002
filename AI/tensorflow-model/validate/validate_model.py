import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

from data.extract_data import fetch_speech_data_in_mfcc

MODEL_PATH = 'cnn_kws_model'
BATCH_SIZE = 64

TARGET_COMMANDS = ['go', 'on', 'stop', 'up', 'down', '_silence_', '_unknown_']


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
    accuracy, cm = evaluate_model()

    print(f'Test accuracy: {accuracy * 100.0:.2f}%')
    print('Confusion matrix (rows=true, cols=pred):')
    print_confusion_matrix(cm, TARGET_COMMANDS)


if __name__ == '__main__':
    main()
