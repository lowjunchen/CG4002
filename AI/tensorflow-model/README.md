# Keyword Spotting (KWS) CNN — TensorFlow Model

This directory contains the end-to-end TensorFlow pipeline for the CNN-based keyword spotting model used by the Ultra96 inference stack. It covers:

1. Preparing data (custom recordings + Google Speech Commands padding)
2. Training the CNN
3. Validating the trained model
4. Exporting fused weights as C headers for HLS
5. Exporting a single sample + expected logits as an HLS test bench

Target commands (7 classes, label index in parentheses):
`start(0)`, `end(1)`, `play(2)`, `pause(3)`, `faster(4)`, `slower(5)`, `unknown(6)`.

Audio format expected everywhere: mono, 8 kHz, 1 second, converted to a `(98, 13)` MFCC (25 ms frame, 10 ms hop, 13 coefficients). The original 16 kHz Speech Commands clips are decimated by a factor of 2 before MFCC.

## Directory layout

```
tensorflow-model/
├── data/
│   ├── extract_data.py           # dataset prep (TFDS + custom)
│   ├── training_data/<label>/    # your recorded .wav files
│   ├── test_wav_samples/<label>/ # held-out .wav files for validation
│   ├── tensorflow_datasets/      # TFDS cache (auto-created)
│   └── processed/                # .npz outputs (auto-created)
├── model/cnn_model.py            # Keras model definition
├── train/train.py                # training entry point
├── validate/validate_model.py    # evaluation + metrics
└── utils/
    ├── export_kws_weights.py     # Conv/BN fusion → .h headers for HLS
    └── extract_test_bench.py     # single-sample MFCC + logits for HLS TB
```

Run every command from the `tensorflow-model/` directory so that the package-style imports (`data.extract_data`, `model.cnn_model`, ...) resolve.

## 1. Prepare the data — [data/extract_data.py](data/extract_data.py)

### 1a. Layout your custom recordings

Place your own `.wav` recordings under `data/training_data/<label>/` where `<label>` is one of the 7 classes. Any subdirectory nesting is allowed — the loader recurses.

```
data/training_data/
├── start/*.wav
├── end/*.wav
├── play/*.wav
├── pause/*.wav
├── faster/*.wav
├── slower/*.wav
└── unknown/*.wav
```

Per-class sample counts are fixed in `SAMPLES_PER_CLASS` (200 for each command, 600 for `unknown`). If you provide fewer local samples for `unknown`, the pipeline pads from Google's Speech Commands `_unknown_` label automatically (`TFDS_PADDING_LABELS`).

### 1b. Build the processed `.npz`

```bash
python -m data.extract_data
```

This runs `prepare_custom_training_data()`, which:

- Loads each folder's `.wav` files and computes MFCCs via `compute_mfcc_wav`.
- Pads `unknown` from TFDS if you are short on samples (downloaded to `data/tensorflow_datasets/` on first run).
- Shuffles, stacks, and writes `data/processed/custom_kws_dataset.npz` containing `train_mfcc` (N, 98, 13) and `train_labels` (N,).

Use `load_custom_dataset(npz_path, batch_size, augment)` elsewhere to get a `tf.data.Dataset` with optional runtime augmentation (time shift, Gaussian noise, SpecAugment-style frequency/time masking).

### 1c. (Optional) Inspect Google Speech Commands

Helpers for exploration, not required for training:

- `inspect_speech_command_data()` — prints dataset info and label map.
- `fetch_one_tfds_sample()` — pulls a single example.
- `fetch_speech_data_in_wav()` — exports one `.wav` per target label.
- `fetch_speech_data_in_mfcc()` — builds MFCC `tf.data` pipelines from TFDS directly (kept for reference; the production path uses the custom `.npz`).

## 2. Train the model — [train/train.py](train/train.py)

```bash
python -m train.train
```

This will:

1. Load `data/processed/custom_kws_dataset.npz` via `load_custom_dataset(batch_size=32, augment=True)`.
2. Build the CNN from [model/cnn_model.py](model/cnn_model.py) using the MFCC input shape `(98, 13, 1)` and 7 classes.
3. Compile with Adam (`lr=1e-3`) and `SparseCategoricalCrossentropy(from_logits=True)`.
4. Train up to 150 epochs with `ReduceLROnPlateau` (factor 0.5, patience 5) and `EarlyStopping` (patience 8, `restore_best_weights=True`), both monitoring `acc`.
5. Save the trained Keras model to `cnn_kws_model/` in the current working directory.

To change epochs or learning rate, call `train_kws_model(train_ds, epochs=..., lr=...)` directly instead of running the script.

## 3. Validate the model — [validate/validate_model.py](validate/validate_model.py)

Put held-out recordings under `data/test_wav_samples/<label>/`. By default `main()` points at that directory:

```bash
python -m validate.validate_model
```

What this does:

- Loads `cnn_kws_model/`.
- For each `.wav`, `chunk_wav_to_mfccs` splits it into overlapping 1-second windows (default overlap 0.5) and runs inference on each window.
- Predicts one label per file using the argmax of the average softmax across windows.
- Prints a per-file table (file, true label, prediction, confidence, `<-- WRONG` marker).
- Computes overall accuracy.
- With `plot_cm=True` prints a confusion matrix.
- With `plot_roc=True` saves per-class one-vs-rest ROC curves to `roc_curves.png`.

Other useful entry points in this file:

- `evaluate_wav(path)` — segment-level predictions for a single `.wav`.
- `evaluate_model()` — evaluate against the custom `.npz` dataset (no augmentation) and return `(accuracy, confusion_matrix, y_true, y_probs)`.

## 4. Export HLS weights — [utils/export_kws_weights.py](utils/export_kws_weights.py)

Converts the trained Keras model into C header files for the HLS accelerator. Conv2D layers immediately followed by BatchNormalization are **fused** (BN folded into the kernel and bias) so the HLS kernel only needs conv + bias + activation.

```bash
python -m utils.export_kws_weights
```

Output: `hls_weights/<layer>_w.h` and `hls_weights/<layer>_b.h`, one pair per Conv2D (fused with BN where present) and Dense layer. Each header includes `kws_hls.h` and defines a flattened `static const data_t <layer>_{w,b}[...]` array in scientific notation.

Toggle `EXPORT_CSV` / `EXPORT_NPY` at the top of the file to also emit `.csv` / `.npy` dumps for debugging.

## 5. Generate an HLS test bench — [utils/extract_test_bench.py](utils/extract_test_bench.py)

Produces a matched input/expected-output pair for the HLS simulation:

```bash
python -m utils.extract_test_bench
```

This:

1. Loads `cnn_kws_model/` and pulls one batch-of-one sample from `load_custom_dataset(batch_size=1, augment=False)`.
2. Writes the flattened 98×13 MFCC to `hls_tb_io/mfcc_in_0.csv`.
3. Runs the sample through the model and writes the 7 logits to `hls_tb_io/logits_out_0.csv`.

Change `num_samples` in the `__main__` block to extract more samples — note the current implementation only keeps the **last** sample iterated, so adjust the loop if you need multiple files.

## End-to-end quick reference

```bash
cd AI/tensorflow-model

# 1. Build the training dataset
python -m data.extract_data

# 2. Train (saves cnn_kws_model/)
python -m train.train

# 3. Validate against held-out wavs
python -m validate.validate_model

# 4. Export fused weights as C headers
python -m utils.export_kws_weights

# 5. Export an HLS test bench sample
python -m utils.extract_test_bench
```

## Dependencies

- `tensorflow`, `tensorflow_datasets`
- `numpy`, `scipy` (for `decimate`)
- `scikit-learn`, `matplotlib` (validation metrics + ROC plots)

First run of anything that touches TFDS will download Google Speech Commands into `data/tensorflow_datasets/`.
