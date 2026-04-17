# Ultra96 PYNQ App — KWS Inference Pipeline

This package runs the CNN keyword-spotting accelerator on the Ultra96 (Zynq UltraScale+). The HLS IP exported from [../../rtl-model](../../rtl-model) is consumed via a `.bit` + `.hwh` overlay in [../overlay/](../overlay/); MFCC pre-processing and DMA transfer are handled in Python.

Everything here is meant to run **on the Ultra96 itself** (PYNQ image), not on a dev machine — `pynq.PL`, the overlay, and the DMA will not import elsewhere.

## Directory layout

```
pynq_app/
├── scripts/
│   ├── capture_mic_wav.py   # MQTT sniffer → .wav (debug only)
│   ├── run_model.py         # single-shot inference on a local .wav
│   └── run_pipeline.py      # live MQTT → inference → MQTT pipeline
├── src/
│   ├── audio_buffer.py      # rolling buffer + windowing
│   ├── config.py            # IN_LEN, OUT_LEN, AXIS_W constants
│   ├── dma_control.py       # AXI-Stream DMA transfer helper
│   ├── inference.py         # MFCC → DMA → softmax → label
│   ├── mqtt_client.py       # mTLS paho-mqtt wrapper
│   ├── mqtt_handlers.py     # VoiceDataCollector
│   ├── overlay_loader.py    # loads .bit / .hwh, grabs DMA handle
│   └── power_manager.py     # CPU governor profiles
└── utils/
    ├── postprocess_data.py  # logits_to_label
    └── preprocess_data.py   # load_wav_windows, compute_mfcc_np
```

All three scripts add both the repo root and `AI/ultra96/` to `sys.path`, so run them as modules from **`AI/ultra96/`** so the `pynq_app.src.*` imports resolve:

```bash
cd AI/ultra96
python -m pynq_app.scripts.<script_name> [...args]
```

## Prerequisites on the Ultra96

1. **Overlay** — `.bit` and `.hwh` present in [../overlay/](../overlay/). `overlay_loader.load_overlay()` maps the DMA from the hardware hand-off file.
2. **mTLS certificates** — for any MQTT script. Defaults point at the repo's broker certs:
   - CA: `Comms/mosquitto/certs/ca.crt`
   - Client cert: `Comms/mosquitto/certs/clients/simulator.crt`
   - Client key: `Comms/mosquitto/certs/clients/simulator.key`
   Override with `--mqtt-ca`, `--mqtt-cert`, `--mqtt-key`.
3. **Broker** — an mTLS Mosquitto broker reachable from the Ultra96 (default `localhost:18883`).
4. **Audio contract** — int16 PCM, mono, 8 kHz; each 1-second window becomes a `(98, 13)` MFCC matching the training pipeline.

## 1. Capture audio over MQTT — [scripts/capture_mic_wav.py](scripts/capture_mic_wav.py)

Debug-only: subscribes to the headset audio topic, buffers int16 samples, and writes a `.wav`. Use this to verify the microphone / publisher is alive **before** touching the inference pipeline.

```bash
cd AI/ultra96
python -m pynq_app.scripts.capture_mic_wav \
    --mqtt-host <broker> \
    --mqtt-port 18883 \
    --mqtt-sub-topic audio/headset/3 \
    --duration 10
```

Output: `pynq_app/data/capture_<timestamp>.wav` (or the path passed to `--output`). The script prints per-packet counts and a summary with peak / RMS amplitude — a peak under 100 triggers a "microphone may be silent" warning.

Relevant flags:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--mqtt-sub-topic` | `audio/headset/3` | Topic to subscribe to |
| `--duration` | `10` | Seconds to capture before saving |
| `--output` | timestamped file in `data/` | Override output path |
| `--mqtt-tls-insecure` | off | Skip broker hostname verification |

## 2. Single-shot inference on a local WAV — [scripts/run_model.py](scripts/run_model.py)

Loads the overlay, chunks a local `.wav` into 1-second windows, runs inference on each window, and keeps the highest-confidence prediction. Use this to validate the accelerator end-to-end without MQTT.

```bash
cd AI/ultra96
python -m pynq_app.scripts.run_model \
    --input_path pynq_app/data/capture_<timestamp>.wav
```

What it does:

1. `apply_profile(pre_profile)` — CPU governor to `performance` by default.
2. `PL.reset()` + `load_overlay()` — programs the bitstream and gets the DMA handle.
3. `load_wav_windows(input_path)` — preprocess into 1-second windows.
4. `run_inference_on_windows(windows, dma)` — DMA each MFCC, softmax, argmax; returns the best `(label, confidence)` across windows.
5. Writes `data/output/result.json` and `data/output/result.txt` (prediction, timings, window count).
6. `apply_profile(post_profile)` — drops CPU governor back to `powersave` by default.

Flags: `--pre_profile` / `--post_profile` each accept `performance` or `powersave`.

## 3. Live MQTT pipeline — [scripts/run_pipeline.py](scripts/run_pipeline.py)

Main entry point. Streams int16 packets from the headset topic into an `AudioBuffer`, runs inference when enough samples have accumulated, and publishes the result as JSON.

```bash
cd AI/ultra96
python -m pynq_app.scripts.run_pipeline \
    --mqtt-host <broker> \
    --mqtt-port 18883 \
    --mqtt-sub-topic audio/headset/3 \
    --mqtt-pub-topic ai/ultra96/result
```

Pipeline loop:

1. Sets the pre-inference power profile and loads the overlay.
2. `AudioBuffer(window_size=8000, hop_size=6400)` — 1-second windows with 0.8 s hop (~20% overlap).
3. `VoiceDataCollector` appends each MQTT packet into the buffer.
4. When `collector.is_ready(min_samples=--min-samples)`, pulls all complete windows, runs `run_inference_on_windows`, and publishes:
   - Success → `{"status":"SUCCESS","result":<label>,"confidence":<float>,"windows":<int>}`
   - No complete window → `{"status":"FAILED","info":"Insufficient audio data"}`
5. Resets the collector and goes back to waiting.

Stop with `Ctrl+C` — the `finally` block disconnects MQTT and restores the post-inference power profile.

Common flags:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--mqtt-sub-topic` | `audio/headset/3` | Incoming audio topic |
| `--mqtt-pub-topic` | `ai/ultra96/result` | Where results are published |
| `--min-samples` | `8000` (1 s) | Minimum buffered samples before inference |
| `--pre-profile` / `--post-profile` | `performance` / `powersave` | CPU governor around active work |
| `--mqtt-tls-insecure` | off | Skip broker hostname verification |

## Typical debug flow

1. **Sanity check MQTT audio**
   `python -m pynq_app.scripts.capture_mic_wav --duration 10`
   → open the saved `.wav`, confirm it's not silent.
2. **Sanity check the accelerator**
   `python -m pynq_app.scripts.run_model -i pynq_app/data/capture_<timestamp>.wav`
   → confirm a sensible label + confidence and check `data/output/result.json`.
3. **Run the live pipeline**
   `python -m pynq_app.scripts.run_pipeline`
   → monitor the publish topic `ai/ultra96/result`.

If step 1 fails, the broker or publisher is the problem; if step 2 fails, the overlay / weights / preprocessing are the problem; only then should step 3 be expected to work.
