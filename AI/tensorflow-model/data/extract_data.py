from utils.convert_to_mfcc import compute_mfcc_np
from utils.write_wav import write_wav_int16

import tensorflow as tf
import tensorflow_datasets as tfds
import os 
import numpy as np

SAMPLE_RATE = 16000
NUM_FRAMES = 98 #Assumeing 1 second audio clips with 25ms frame length and 10ms frame step
NUM_MFCC = 13


def inspect_speech_command_data(dataset_name='speech_commands', split='test', data_dir=None):
    """
    Inspect the speech commands dataset from TensorFlow Datasets.

    :param dataset_name: Name of the dataset to load (default: 'speech_commands')
    :param split: Which split to inspect (default: 'test')
    :param data_dir: Optional directory to store the dataset
    """
    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')

    # Load the dataset
    dataset, info = tfds.load(
        dataset_name, 
        split=split, 
        with_info=True, 
        data_dir=data_dir)
    
    # Display dataset information
    print(f"Dataset: {dataset_name} (v{info.version})")
    print(f"Split: {split}")
    print(f"Total samples: {info.splits[split].num_examples:,}")
    print(f"Audio specs: {info.features['audio']}")
    print()

    # Display label information
    label_feature = info.features['label']
    print(f"Total classes: {label_feature.num_classes}")
    print("\nLabel index → class name:")
    print("-" * 40)
    for idx, name in enumerate(label_feature.names):
        print(f"{idx:2d} → {name}")
    print()

def fetch_one_tfds_sample(dataset_name="speech_commands", split="test", data_dir=None):
    """
    Fetch one sample from the specified TFDS dataset split.
    
    :param dataset_name: Name of the dataset to load (default: 'speech_commands')
    :param split: Which split to fetch from (default: 'test')
    :param data_dir: Optional directory to store the dataset

    :return: Tuple of (audio, label_idx, label_name)
    """
    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')

    dataset, info = tfds.load(
        dataset_name, 
        split=split, 
        with_info=True, 
        data_dir=data_dir)
    label_names = info.features['label'].names
    
    for ex in dataset.take(1):
        audio = ex['audio'].numpy()
        label_idx = ex['label'].numpy()
        label_name = label_names[label_idx]
        print(f"Audio shape: {audio.shape}, Label index: {label_idx}, Label name: {label_name}")

        return audio, label_idx, label_name

def fetch_speech_data_in_mfcc(
        dataset_name="speech_commands",
        data_dir=None,
        train_split="train",
        test_split="test",
        batch_size=64,
        shuffle_buffer_size=1000,
        seed=1234
):
    """
    Filter the speech commands dataset and preprocess it into MFCC features.

    :param dataset_name: Name of the dataset to load 
    :param data_dir: Optional directory to store the dataset
    :param train_split: Which split to use for training 
    :param test_split: Which split to use for testing 
    :param batch_size: Batch size for training and testing 
    :param shuffle_buffer_size: Buffer size for shuffling the training data
    :param seed: Random seed for shuffling

    :return: Tuple of (train_dataset, test_dataset) where each dataset yields (mfcc, label) pairs
    """

    #Training data will now make use of these commands: "go", "on", "stop", "up", "down", "_silence_" and "_unknown_"
    target_commands = ['go', 'on', 'stop', 'up', 'down', '_silence_', '_unknown_']

    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')
    
    train_ds, info = tfds.load(
        dataset_name, 
        split=train_split, 
        with_info=True, 
        data_dir=data_dir)
    
    test_ds = tfds.load(
        dataset_name,
        split=test_split,
        data_dir=data_dir)

    label_names = info.features["label"].names
    name_to_idx = {n: i for i, n in enumerate(label_names)}

    keep_ids = tf.constant([name_to_idx[name] for name in target_commands], dtype=tf.int64)

    tfds_to_compact = -1 * np.ones(shape=(len(label_names),), dtype=np.int64)
    for compact_idx, name in enumerate(target_commands):
        tfds_to_compact[name_to_idx[name]] = compact_idx
    tfds_to_compact_tf = tf.constant(tfds_to_compact, dtype=tf.int64)

    #Helper functions
    def keep_only_targets(ex):
        lbl = tf.cast(ex['label'], tf.int64)
        return tf.reduce_any(tf.equal(lbl, keep_ids))
    
    def audio_to_mfcc(audio_int16):
        def _np_mfcc(audio_np):
            mfcc = compute_mfcc_np(audio_np)
            return mfcc.astype(np.float32)

        mfcc = tf.numpy_function(_np_mfcc, [audio_int16], tf.float32)
        mfcc.set_shape((NUM_FRAMES, NUM_MFCC))
        mfcc = tf.expand_dims(mfcc, axis=-1) #Add channel dimension for CNN input
        return mfcc

    def preprocess(ex):
        mfcc = audio_to_mfcc(ex['audio'])
        label = tf.gather(tfds_to_compact_tf, tf.cast(ex['label'], tf.int64))
        return mfcc, label

    train_out = (
        train_ds
        .filter(keep_only_targets)
        .map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
        .shuffle(shuffle_buffer_size, seed=seed)
        .batch(batch_size)
        .prefetch(tf.data.AUTOTUNE)
    )

    test_out = (
        test_ds
        .filter(keep_only_targets)
        .map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
        .batch(batch_size)
        .prefetch(tf.data.AUTOTUNE)
    )

    for mfcc, label in train_out.take(1):
        print("MFCC batch shape:", mfcc.shape)
        print("MFCC dtype:", mfcc.dtype)
        print("Label batch shape:", label.shape)
        print("Labels:", label.numpy())

    for mfcc, label in test_out.take(1):
        print("MFCC batch shape:", mfcc.shape)
        print("MFCC dtype:", mfcc.dtype)
        print("Label batch shape:", label.shape)
        print("Labels:", label.numpy())

    """     
    num_train_samples = 0
    for _ in train_out.unbatch():
        num_train_samples += 1

    num_test_samples = 0
    for _ in test_out.unbatch():
        num_test_samples += 1

    print("Train samples:", num_train_samples)
    print("Test samples :", num_test_samples)
    """
    return train_out, test_out

def fetch_speech_data_in_wav(
        dataset_name="speech_commands",
        data_dir=None,
        split="test",
        output_dir="data/wav_samples",
        seed = 1234
):
    target_commands = ['go', 'on', 'stop', 'up', 'down', '_silence_', '_unknown_']
    
    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')

    ds, info = tfds.load(dataset_name, split=split, with_info=True, data_dir=data_dir)
    label_names = info.features["label"].names

    rng = np.random.default_rng(seed)

    got = {k: False for k in target_commands}
    saved_paths = {}

    for ex in tfds.as_numpy(ds):
        audio = ex["audio"]         
        label_idx = int(ex["label"])
        label_name = label_names[label_idx]

        if label_name in target_commands and not got[label_name]:
            path = os.path.join(output_dir, f"{label_name}.wav")
            write_wav_int16(path, audio, SAMPLE_RATE)
            got[label_name] = True
            saved_paths[label_name] = path

        if all(got.values()):
            break

    print("Saved:")
    for k in target_commands:
        if k in saved_paths:
            print(f"  {k:10s} -> {saved_paths[k]}")
    

if __name__ == "__main__":
    fetch_speech_data_in_wav()