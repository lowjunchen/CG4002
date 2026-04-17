# KWS HLS Model (Vitis HLS)

This folder holds the HLS sources for the CNN keyword-spotting accelerator that runs on the Ultra96 (Zynq UltraScale+ `xazu3eg-sbva484-1-i`). It consumes the weights and test-bench artifacts produced by the TensorFlow pipeline in [../tensorflow-model](../tensorflow-model).

## Directory layout

```
rtl-model/
├── src/
│   ├── hls_config.cfg     # Vitis HLS config (part, clock, file list, top)
│   ├── kws_hls.h          # fixed-point types (data_t, axis_t)
│   ├── kws_layers.h       # conv / BN / pool / dense primitives
│   ├── kws_top.cpp        # top-level dataflow function
│   └── kws_top.h          # kws_top prototype (AXI-Stream I/O)
└── tb/
    └── tb_kws_top.cpp     # C/RTL co-sim test bench
```

`hls_config.cfg` already lists the expected file names — if you rename anything, update it too.

## Prerequisites — files produced by the TensorFlow pipeline

Before opening the HLS project, generate these in the `tensorflow-model/` directory:

| Where in HLS project | File(s) | Produced by |
| --- | --- | --- |
| `<project>/src/` (alongside `kws_top.cpp`) | `conv2d_w.h`, `conv2d_b.h`, `conv2d_1_w.h`, `conv2d_1_b.h`, `conv2d_2_w.h`, `conv2d_2_b.h`, `dense_w.h`, `dense_b.h` | [../tensorflow-model/utils/export_kws_weights.py](../tensorflow-model/utils/export_kws_weights.py) → `hls_weights/` |
| `<project>/testbench/` | `tb_kws_top.cpp` | This repo — [tb/tb_kws_top.cpp](tb/tb_kws_top.cpp) |
| `<project>/testbench/tb/io/` | `mfcc_in_0.csv`, `logits_out_0.csv` | [../tensorflow-model/utils/extract_test_bench.py](../tensorflow-model/utils/extract_test_bench.py) → `hls_tb_io/` |

The test bench resolves inputs relative to the HLS working directory using `tb/io/mfcc_in_0.csv` and `tb/io/logits_out_0.csv` — keep that `tb/io/` subpath exactly.

## Setting up the Vitis HLS project

1. **Create / open the HLS project** targeting `xazu3eg-sbva484-1-i` with a 10 ns clock (matches `hls_config.cfg`).
2. **Add synthesis sources** to the project's source group:
   - All files from [src/](src/): `kws_top.cpp`, `kws_top.h`, `kws_layers.h`, `kws_hls.h`.
   - All weight headers exported by `export_kws_weights.py` — drop them in the **same folder as the other HLS sources** so the `#include "..._w.h" / "..._b.h"` lines resolve. Required files:
     - `conv2d_w.h`, `conv2d_b.h`
     - `conv2d_1_w.h`, `conv2d_1_b.h`
     - `conv2d_2_w.h`, `conv2d_2_b.h`
     - `dense_w.h`, `dense_b.h`
   - Set the **top function** to `kws_top`.
3. **Add test-bench sources**:
   - Place [tb/tb_kws_top.cpp](tb/tb_kws_top.cpp) into the project's **testbench** source group.
   - Place the CSVs from `hls_tb_io/` under **`testbench/tb/io/`**:
     - `testbench/tb/io/mfcc_in_0.csv`
     - `testbench/tb/io/logits_out_0.csv`

Final structure inside the HLS project:

```
<hls_project>/
├── src/ (synthesis)
│   ├── kws_top.cpp
│   ├── kws_top.h
│   ├── kws_layers.h
│   ├── kws_hls.h
│   ├── conv2d_w.h
│   ├── conv2d_b.h
│   ├── conv2d_1_w.h
│   ├── conv2d_1_b.h
│   ├── conv2d_2_w.h
│   ├── conv2d_2_b.h
│   ├── dense_w.h
│   └── dense_b.h
└── testbench/
    ├── tb_kws_top.cpp
    └── tb/
        └── io/
            ├── mfcc_in_0.csv
            └── logits_out_0.csv
```

## Running the flow

1. **C Simulation** — runs `tb_kws_top.cpp` against the C model. Expect a pass message:
   `PASS: HLS output matches TensorFlow golden within tolerances.`
   Tolerances are `atol = rtol = 5e-3` (relaxed to absorb BN-fused fixed-point quantization error).
2. **C Synthesis** — synthesizes `kws_top` with AXI-Stream `axis_t` I/O.
3. **C/RTL Co-simulation** — reuses the same test bench to validate the RTL.
4. **Export IP** — `ip_catalog` format (set by `hls_config.cfg`); drop the resulting IP into your Vivado block design for the Ultra96.

## I/O contract (must match the TensorFlow side)

- **Input stream** `s_in`: `IN_H * IN_W = 98 * 13 = 1274` elements in h-major, then w order. `TLAST` on the final beat.
- **Output stream** `s_out`: `NUM_CLASSES = 7` logits. `TLAST` on the final beat.
- Element type is `data_t` (fixed-point, defined in `kws_hls.h`); the test bench converts to/from `float` for CSV comparison.

If you change `IN_H`, `IN_W`, or `NUM_CLASSES`, regenerate the test-bench CSVs from TensorFlow so lengths stay in sync — the test bench hard-fails on mismatch.

## Regenerating artifacts

From `AI/tensorflow-model/`:

```bash
python -m utils.export_kws_weights    # -> hls_weights/*.h   (copy into src/ of HLS project)
python -m utils.extract_test_bench    # -> hls_tb_io/*.csv   (copy into testbench/tb/io/)
```

Re-run these whenever you retrain the model, otherwise the test bench will diverge from the DUT.
