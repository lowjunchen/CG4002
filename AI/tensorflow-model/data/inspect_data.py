import tensorflow as tf
import tensorflow_datasets as tfds
import os 
import numpy as np

def inspect_speech_command_data(dataset_name='speech_commands', split='test', data_dir=None):
    if data_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, 'tensorflow_datasets')

    # Load the dataset
    dataset, info = tfds.load(
        dataset_name, 
        split=split, 
        with_info=True, 
        data_dir=data_dir)
    
    # === Dataset Overview ===
    print(f"Dataset: {dataset_name} (v{info.version})")
    print(f"Split: {split}")
    print(f"Total samples: {info.splits[split].num_examples:,}")
    print(f"Audio specs: {info.features['audio']}")
    print()

    # === Label Classes ===
    label_feature = info.features['label']
    print(f"Total classes: {label_feature.num_classes}")
    print("\nLabel index → class name:")
    print("-" * 40)
    for idx, name in enumerate(label_feature.names):
        print(f"{idx:2d} → {name}")
    print()

    #Training data will now make use of these commands: "go", "on", "stop", "up", "down", "_silence_" and "_unknown_"
    target_commands = np.array(['go', 'on', 'stop', 'up', 'down', '_silence_', '_unknown_'])

def fetch_one_tfds_sample(dataset_name="speech_commands", split="test", data_dir=None):
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

if __name__ == "__main__":
    inspect_speech_command_data()