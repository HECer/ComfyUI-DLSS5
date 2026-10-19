# Fast depth model selection

Use **DLSS Depth Guide (Model Selection)** when you want to choose the guide model explicitly. Its model tooltip explains every option; `model_info` reports the choice, effective precision, input size and setup-inclusive elapsed time. Connect `depth` to the same SR/NR inputs as the existing DA-V2 guide.

**Experimental DLSS — Easy Upscale & Render** also has optional `depth_model`, `depth_input_size`, `depth_precision`, `motion_model` and `motion_input_size` controls. `Preset (unchanged)`, size `0` and `FP32` preserve its existing guide settings. Existing saved workflows keep their required widgets and numerical defaults.

## Choose a model

| Model | Why choose it | Tradeoff |
|---|---|---|
| Depth Anything V2 Small | Established general-purpose baseline, 24.8M parameters | Independent frame predictions can flicker |
| Depth Anything V2 Base / Large | Compare higher-capacity depth predictions | More compute and VRAM; checkpoint terms restrict commercial use |
| YOLO26 Nano | Speed-first experiment, 6.3M parameters | Less detail; no intrinsic video consistency; optional Ultralytics |
| YOLO26 Small | More detail than Nano, 13.2M parameters | More compute than Nano; same optional dependency |
| Video Depth Anything Small | Temporally consistent video depth, 28.4M parameters | Its own temporal windows, source download and memory costs |

Weights download on first use. YOLO checkpoints are stored under ComfyUI's `models/dlss5/yolo26`; standalone runs use `HF_HOME/dlss5/yolo26` (or the Hugging Face cache directory when `HF_HOME` is unset). The node converts YOLO's metric depth to near-bright inverse depth before normalization. Shared clip normalization reduces range changes; it does not make a single-frame model temporally consistent. Easy also retains its motion-based temporal stabilization for video.

For the first speed comparison, try **YOLO26 Nano**, `depth_input_size=392`, `depth_precision=FP16`, **Optical Flow (fastest)** and `motion_input_size=512`. Compare against **DA-V2 Small**, size `280` or `392`, FP16. These are experimental settings, not a 4K/30 guarantee. Smaller depth and motion inputs lose fine edges and small movements. Motion vectors stay in the existing current-to-previous, frame-relative encoding when resized.

DA-V2/VDA input sizes target the short side and round according to their model preprocessing (DA-V2 uses multiples of 14). YOLO sizes target the long side and round up to a multiple of 32, so `392` becomes `416`. Size `0` uses the model default: 518 for DA-V2/VDA and 768 for YOLO. All guides return the original input dimensions. FP16 uses CUDA; CPU runs use FP32 and say so. VDA always normalizes across its clip and manages its own batching.

## Optional YOLO setup

The default installation does not require Ultralytics or TensorRT. A missing or old Ultralytics installation fails with instructions before downloading weights. Execution never installs packages or replaces Torch. Selecting YOLO disables Ultralytics automatic package installation for the host process, including already imported dependency checkers; other Ultralytics users in that process must install missing dependencies explicitly too.

YOLO26 depth requires an Ultralytics version that exports `ultralytics.models.yolo.depth.DepthPredictor` (tested here with 8.4.182). In a separate test environment matching your existing Torch/CUDA build, install the optional package and verify the import:

```powershell
python -m pip install "ultralytics==8.4.182"
python -c "from ultralytics.models.yolo.depth import DepthPredictor; print('Depth support available')"
```

Do not run a package upgrade across your production ComfyUI environment just to resolve a dependency conflict. Check the installer's dependency plan first or use a separate environment. Ultralytics publishes [AGPL-3.0 and commercial licensing information](https://www.ultralytics.com/license); see its terms before choosing it for your deployment. DA-V2 Small and VDA Small remain available without Ultralytics.

For an existing compatible TensorRT setup, export the selected model on the target GPU. Example for a fixed batch of four and a 416 input:

```python
from ultralytics import YOLO
YOLO("yolo26n-depth.pt").export(format="engine", imgsz=416, batch=4, half=True)
```

Set the new guide node's `engine_path` to that `.engine` file, select the matching YOLO model, set `input_size=392` (rounded to 416), and match `chunk_size` and input frame count to the engine's supported batch profile. Fixed-batch engines may reject a final partial batch; use a compatible dynamic profile or a matching batch. Engines depend on the GPU and TensorRT build. Precision, shape and batch limits come from the engine export; the precision dropdown does not rebuild an engine. The adapter checks file presence and CUDA, but cannot verify the checkpoint identity baked into an engine. Engines are supported by the explicit guide node; Easy uses PyTorch.

## Measure the 4K target

The target is **3840x2160 output above 30 processed source frames per second** on the RTX 5090. For 2x SR, measure 1920x1080 input. For NR-only processing of native 4K footage, measure 3840x2160 input separately. Interpolated frames do not count toward processing throughput.

Run with the Python that actually provides CUDA and a configured native bridge:

```powershell
python tools/benchmark_fast_depth.py --model "Depth Anything V2 Small" --input-size 280 --precision FP16 --image docs/images/benchmark-rainy-city-source.png --output ../test-output/fast-depth/da-small.json
python tools/benchmark_fast_depth.py --model "YOLO26 Nano (optional)" --input-size 392 --precision FP16 --image docs/images/benchmark-rainy-city-source.png --output ../test-output/fast-depth/yolo-nano.json
```

Use `--depth-only` to isolate guide throughput; this never establishes the complete pipeline gate. The default full run includes depth, 512-side optical flow, temporal stabilization, 2x SR, NR, native process startup and CPU IMAGE boundaries. The JSON records a cold run separately, one warmup by default, three measured samples, the empirical range and median, output dimensions and inclusive stage times. Nested stage times must not be added together. The gate requires exactly 3840x2160 output and median source throughput strictly above `--minimum-fps` (default 30). Exit code 2 means either condition failed; exit code 1 means a runtime failure left the gate unverified.

These runs repeat a still with synthetic motion. They measure throughput, not real-video quality. Loading/decoding, queue wait and saving/encoding are outside the timer. Model downloads and cold initialization occur in the separately reported cold run. Unknown waiting time is not a speed estimate. A release claiming complete video-file throughput must measure decoding and encoding too, and validate representative real clips, scene cuts, fast motion, occlusions and fine geometry.

The optional [persistent NR worker](NATIVE_WORKER.md) can retain matching NR initialization between requests. Compare it using `--native-mode "Persistent NR worker (reuse initialization)"`; the default remains isolated and SR always stays isolated.

## Published speeds and other candidates

Ultralytics reports model-only T4 TensorRT FP16 timings at roughly 768 pixels: YOLO26 Nano 2.73 ms, Small 3.82 ms, DA-V2 Small 20.99 ms. That is a published Nano speedup of 7.7x in that specific harness, excluding preprocessing and postprocessing. It is not a prediction for PyTorch, RTX 5090 or this native bridge. See the [official benchmark and methodology](https://docs.ultralytics.com/tasks/depth#speed-compared-to-depth-anything-v2).

[oVDA](https://github.com/FriedFeid/OnlineVideoDepthAnything) is a useful future temporal-backend candidate; its [paper](https://arxiv.org/abs/2510.09182) reports 42 FPS on A100. It is not integrated by this change. [FlashDepth](https://github.com/Eyeline-Labs/FlashDepth) is already available through the external node and reports 24.12 FPS at 2044x1148 on A100; its external adapter's temporary video I/O adds overhead. [DA3 Small](https://github.com/ByteDance-Seed/Depth-Anything-3) is another quality/geometry candidate, but there is no matched local evidence that it improves this speed target. Native bridge initialization, CPU/GPU copies, motion estimation and stabilization can dominate even when depth is fast.

## Local verification on 2026-10-19

The selectable-depth implementation before the subsequent NR-worker change was measured with RTX 5090, Torch 2.9.1+cu130 and optional Ultralytics 8.4.182 in a separate package target. The [recorded benchmark](benchmarks/2026-10-19-fast-depth.json) includes source fingerprints and the input checksum.

For YOLO26 Nano FP16, size 392 (rounded to 416), CPU IMAGE input, 512-side optical flow and 2x SR plus NR, three measured two-frame runs produced 3840x2160 output in **28.151–29.437 seconds** each (median **28.452 seconds**, **0.0703 source FPS**). The cold run and one warmup are separate. The 4K/30 gate **failed**. This short-batch measurement is not a prediction for longer clips.

Within those runs, native SR took 9.17–10.56 seconds and NR took 14.60–16.83 seconds. These stages include file transfers, process initialization and inference; the measurements do not isolate GPU kernel time. Depth took 0.119–0.139 seconds per two-frame batch. The data supports investigating the native bridge and its data path before expecting an alternative guide model to make this complete pipeline real time.

The CUDA memory regression passed with a 64-frame 512x768 CPU input, four-frame inference batches and a peak intermediate GPU allocation increase below 128 MiB. It uses a deterministic model substitute to check adapter buffering; this is not total VRAM usage with model weights. Full IMAGE input/output still occupies host memory. Real YOLO Nano and Small inference and ComfyUI model selection/legacy-widget loading were exercised. TensorRT execution and representative real-video visual quality remain unverified.

The subsequent [matched NR-worker comparison](NATIVE_WORKER.md#matched-local-measurement-on-2026-10-20) observed 1.36x complete-node throughput: 0.0570 versus 0.0776 source FPS with three two-frame samples per mode. The 4K/>30 gate still failed. These newer records include fingerprints of the worker and both runners; use them for the current native execution options.
