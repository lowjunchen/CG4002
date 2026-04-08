from utils.convert_to_mfcc import compute_mfcc_np, compute_mfcc_wav
from utils.write_wav import write_wav_int16

import tensorflow as tf
import tensorflow_datasets as tfds
import os
import glob
import numpy as np
from scipy.signal import decimate

ORIGINAL_SAMPLE_RATE = 16000
SAMPLE_RATE = 8000
DOWNSAMPLE_FACTOR = ORIGINAL_SAMPLE_RATE // SAMPLE_RATE
NUM_FRAMES = 98 #Assumeing 1 second audio clips with 25ms frame length and 10ms frame step
NUM_MFCC = 13

# Custom training data label mapping
CUSTOM_LABELS = {'start': 0, 'end': 1, 'play': 2, 'pause': 3, 'faster': 4, 'slower': 5, 'unknown': 6}
SAMPLES_PER_CLASS = {'start': 200, 'end': 200, 'play': 200, 'pause': 200, 'faster': 200, 'slower': 200, 'unknown': 600}

# Labels that can be padded from Google's speech_commands dataset.
# Maps local label name -> speech_commands label name.
TFDS_PADDING_LABELS = {'unknown': '_unknown_'}


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
        training=True,
        batch_size=64,
        shuffle_buffer_size=1000,
        seed=1234
):
    """
    Filter the speech commands dataset and preprocess it into MFCC features.

    :param dataset_name: Name of the dataset to load 
    :param data_dir: Optional directory to store the dataset
    :param train_split: Which split to use for training
    :param test_split: Which split to use for testing when training=False
    :param training: When True, split the TFDS train split into 80:20 train/test.
                     When False, use TFDS train and TFDS test.
    :param batch_size: Batch size for training and testing 
    :param shuffle_buffer_size: Buffer size for shuffling the training data
    :param seed: Random seed for shuffling

    :return: Tuple of (train_dataset, test_dataset) where each dataset yields (mfcc, label) pairs
    """

    #Training data will now make use of these commands: "start", "end", "play", "pause", "faster", "slower" and "unknown"
    target_commands = ['start', 'end', 'play', 'pause', 'faster', 'slower', 'unknown']

    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')
    
    train_ds, info = tfds.load(
        dataset_name, 
        split=train_split, 
        with_info=True, 
        data_dir=data_dir)

    #Build a 80:20 train-test split on the Speech Command's train dataset in training
    if training:
        split_source = (
            train_ds
            .shuffle(shuffle_buffer_size, seed=seed, reshuffle_each_iteration=False)
            .enumerate()
        )

        train_ds = split_source.filter(lambda i, _: tf.less(tf.math.floormod(i, 10), 8)).map(
            lambda _, ex: ex, num_parallel_calls=tf.data.AUTOTUNE
        )
        test_ds = split_source.filter(lambda i, _: tf.greater_equal(tf.math.floormod(i, 10), 8)).map(
            lambda _, ex: ex, num_parallel_calls=tf.data.AUTOTUNE
        )
    else:
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
            audio_np = decimate(audio_np, DOWNSAMPLE_FACTOR).astype(audio_np.dtype)
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
            write_wav_int16(path, audio, ORIGINAL_SAMPLE_RATE)
            got[label_name] = True
            saved_paths[label_name] = path

        if all(got.values()):
            break

    print("Saved:")
    for k in target_commands:
        if k in saved_paths:
            print(f"  {k:10s} -> {saved_paths[k]}")
    

def _load_wav_files_from_folder(folder_path):
    """
    Recursively load all .wav files from a folder (including subfolders)
    and convert each to MFCC.

    :param folder_path: path to the root folder containing .wav files
    :return: list of MFCC arrays, each (NUM_FRAMES, NUM_MFCC)
    """
    wav_files = sorted(glob.glob(os.path.join(folder_path, "**", "*.wav"), recursive=True))
    mfccs = []
    for f in wav_files:
        mfcc = compute_mfcc_wav(f)
        mfccs.append(mfcc.astype(np.float32))
    return mfccs


def _fetch_tfds_padding(tfds_label, num_needed, data_dir=None, seed=1234):
    """
    Fetch `num_needed` samples of a given label from Google's speech_commands
    dataset, downsample from 16kHz to 8kHz, and convert to MFCC.

    :param tfds_label: label name in the speech_commands dataset (e.g. '_unknown_')
    :param num_needed: number of additional samples required
    :param data_dir: optional directory for TFDS cache
    :param seed: random seed for reproducibility
    :return: list of MFCC arrays
    """
    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')

    ds, info = tfds.load("speech_commands", split="train", with_info=True, data_dir=data_dir)
    label_names = info.features["label"].names
    target_idx = label_names.index(tfds_label)

    matched_samples = []
    for ex in tfds.as_numpy(ds):
        if int(ex["label"]) == target_idx:
            matched_samples.append(ex["audio"])
        if len(matched_samples) >= num_needed * 3:
            break

    rng = np.random.default_rng(seed)
    rng.shuffle(matched_samples)
    matched_samples = matched_samples[:num_needed]

    mfccs = []
    for audio in matched_samples:
        audio_ds = decimate(audio, DOWNSAMPLE_FACTOR).astype(np.int16)
        mfcc = compute_mfcc_np(audio_ds).astype(np.float32)
        mfccs.append(mfcc)
    return mfccs


def prepare_custom_training_data(
        training_data_dir=None,
        output_path=None,
        tfds_data_dir=None,
        seed=1234
):
    """
    Process custom training wav files into MFCC features and save as a .npz file.
    All samples are used for training (no test split).

    Labels: {start:0, end:1, play:2, pause:3, faster:4, slower:5, unknown:6}

    Samples per class are defined in SAMPLES_PER_CLASS (150 for most).
    Classes with fewer local samples (unknown) are padded from
    Google's speech_commands dataset.

    :param training_data_dir: root folder with subfolders per label
    :param output_path: path to save the .npz output file
    :param tfds_data_dir: optional TFDS cache directory
    :param seed: random seed for shuffling and selection
    :return: tf.data.Dataset for training
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if training_data_dir is None:
        training_data_dir = os.path.join(script_dir, 'training_data')
    if output_path is None:
        output_path = os.path.join(script_dir, 'processed', 'custom_kws_dataset.npz')

    rng = np.random.default_rng(seed)

    all_mfcc = []
    all_labels = []

    for label_name, label_idx in CUSTOM_LABELS.items():
        n_samples = SAMPLES_PER_CLASS[label_name]
        folder = os.path.join(training_data_dir, label_name)
        mfccs = _load_wav_files_from_folder(folder)
        print(f"  {label_name}: {len(mfccs)} local samples loaded")

        # Pad from speech_commands if this label has a TFDS mapping and needs more data
        if label_name in TFDS_PADDING_LABELS and len(mfccs) < n_samples:
            tfds_label = TFDS_PADDING_LABELS[label_name]
            num_needed = n_samples - len(mfccs)
            print(f"  Padding {label_name} with {num_needed} samples from speech_commands '{tfds_label}'...")
            extra = _fetch_tfds_padding(tfds_label, num_needed, data_dir=tfds_data_dir, seed=seed)
            mfccs.extend(extra)
            print(f"  {label_name}: {len(mfccs)} total samples after padding")

        # Shuffle and select exactly n_samples
        indices = np.arange(len(mfccs))
        rng.shuffle(indices)
        selected = indices[:n_samples]

        for i in selected:
            all_mfcc.append(mfccs[i])
            all_labels.append(label_idx)

    # Stack into arrays
    train_mfcc = np.stack(all_mfcc)     # (1200, 98, 13)
    train_labels = np.array(all_labels, dtype=np.int64)

    # Shuffle
    order = np.arange(len(train_labels))
    rng.shuffle(order)
    train_mfcc = train_mfcc[order]
    train_labels = train_labels[order]

    # Save to .npz
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.savez(
        output_path,
        train_mfcc=train_mfcc,
        train_labels=train_labels,
    )
    print(f"Saved processed dataset to {output_path}")
    print(f"  Train: {train_mfcc.shape} ({len(train_labels)} samples, {len(CUSTOM_LABELS)} classes)")

    train_ds = load_custom_dataset(output_path)
    return train_ds


def _augment_mfcc(mfcc):
    """
    Apply random augmentations to an MFCC tensor for training.
    - Time shift: roll along the time axis
    - Gaussian noise injection
    - Frequency masking: zero out random frequency bands
    - Time masking: zero out random time steps

    :param mfcc: input tensor of shape (98, 13, 1)
    :return: augmented tensor of same shape
    """
    # Time shift: roll by up to ±5 frames
    shift = tf.random.uniform([], -5, 6, dtype=tf.int32)
    mfcc = tf.roll(mfcc, shift=shift, axis=0)

    # Gaussian noise
    noise = tf.random.normal(tf.shape(mfcc), stddev=0.02)
    mfcc = mfcc + noise

    # Frequency masking: zero out 1-3 consecutive frequency bins
    f_width = tf.random.uniform([], 1, 4, dtype=tf.int32)
    f_start = tf.random.uniform([], 0, 13 - 3, dtype=tf.int32)
    freq_mask = tf.concat([
        tf.ones([98, f_start, 1]),
        tf.zeros([98, f_width, 1]),
        tf.ones([98, 13 - f_start - f_width, 1]),
    ], axis=1)
    mfcc = mfcc * freq_mask

    # Time masking: zero out 3-8 consecutive time frames
    t_width = tf.random.uniform([], 3, 9, dtype=tf.int32)
    t_start = tf.random.uniform([], 0, 98 - 8, dtype=tf.int32)
    time_mask = tf.concat([
        tf.ones([t_start, 13, 1]),
        tf.zeros([t_width, 13, 1]),
        tf.ones([98 - t_start - t_width, 13, 1]),
    ], axis=0)
    mfcc = mfcc * time_mask

    return mfcc


def load_custom_dataset(npz_path=None, batch_size=8, augment=True):
    """
    Load a previously saved .npz dataset and return a batched tf.data.Dataset
    ready for training.

    :param npz_path: path to the .npz file
    :param batch_size: batch size for the dataset
    :param augment: whether to apply data augmentation
    :return: tf.data.Dataset yielding (mfcc, label) pairs
    """
    if npz_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        npz_path = os.path.join(script_dir, 'processed', 'custom_kws_dataset.npz')

    data = np.load(npz_path)
    train_mfcc = data['train_mfcc']     # (1200, 98, 13)
    train_labels = data['train_labels']

    # Add channel dimension for CNN: (N, 98, 13) -> (N, 98, 13, 1)
    train_mfcc = train_mfcc[..., np.newaxis]

    train_ds = tf.data.Dataset.from_tensor_slices((train_mfcc, train_labels))
    train_ds = train_ds.shuffle(len(train_labels))
    if augment:
        train_ds = train_ds.map(
            lambda mfcc, label: (_augment_mfcc(mfcc), label),
            num_parallel_calls=tf.data.AUTOTUNE
        )
    train_ds = train_ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    print(f"Loaded dataset from {npz_path}")
    print(f"  Train: {train_mfcc.shape[0]} samples")
    print(f"  Augmentation: {'ON' if augment else 'OFF'}, Batch size: {batch_size}")

    return train_ds


if __name__ == "__main__":
    prepare_custom_training_data()
