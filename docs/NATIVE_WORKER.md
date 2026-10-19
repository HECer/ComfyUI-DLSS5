# Persistent Neural Rendering worker

The optional `native_mode` control on **Easy Pipeline**, **Full Pipeline** and **Neural Rendering** selects how NR runs:

| Mode | Behavior |
|---|---|
| Isolated process (compatible) | Default. Starts a fresh native process for each NR window, preserving existing workflows. |
| Persistent NR worker (reuse initialization) | Retains one NR feature when shape and settings match. The first request initializes; later matching requests reuse it. |

`processing_mode` controls full sequences versus bounded windows; `native_mode` controls the NR helper lifetime.

SR keeps its existing isolated process in both modes. The control is ignored for Easy's **Upscale only** operation. Reusing an SR feature failed the independent-sequence output comparison, even with frame caches disabled, so it is excluded from this optimization. The cause within native feature state is not established.

Each NR request starts at frame zero and resets the native temporal history. Input and output frame caching is disabled for the mutable graph; new color, depth and motion arrays replace the previous request's inputs. Still images retain the existing two-frame warmup and return the final frame. Bounded windows retain their existing chronology, overlap and numerical presets.

A worker retains GPU resources until 120 seconds idle or the host exits. While retained, those resources compete with other models and with the isolated SR process. Cancellation, timeout or native failure kills and reaps the helper; the next request initializes again. Changing input shape or NR settings replaces the cached feature. Changing the interpreter path or the runner, worker, plugin or snippet file identity restarts the process. Progress and bounded error/timeout log tails reach ComfyUI. Runtime reports distinguish `initialization=created` from `initialization=reused`.

## Native equivalence

The [2026-10-20 native comparison](benchmarks/2026-10-20-native-equivalence.json) records seven real bridge comparisons against separate isolated references on RTX 5090: 4K A→B→A with changed colors and guides, a still image, a two-frame sequence after the still, changed settings and a reduced resolution. All outputs were pixel-identical, maximum absolute error **0**. This validates these cases; it does not establish perceptual quality on representative videos.

Run the explicit native test with your existing configured bridge:

```powershell
$env:DLSS5_NATIVE_TESTS = "1"
$env:DLSS5_NATIVE_TEST_SIZE = "4k"
python -m pytest tests/test_native_worker_real.py -q -s
```

Without the opt-in environment variable, ordinary offline tests skip native inference. The test creates isolated references and uses the installed DLLs; it does not install or replace runtimes.

## Throughput

Compare both modes with the same [full-pipeline benchmark](FAST_DEPTH.md#measure-the-4k-target). For example:

```powershell
python tools/benchmark_fast_depth.py --model "YOLO26 Nano (optional)" --input-size 392 --precision FP16 --frames 2 --image docs/images/benchmark-rainy-city-source.png --native-mode "Persistent NR worker (reuse initialization)" --output ../test-output/native-worker.json
```

The JSON separates a cold request, warmups and three measured samples. It includes node/guide/native source fingerprints and the selected mode. Reuse avoids repeated NR initialization; it does not remove SR initialization, CPU/GPU transfers, temporary arrays or native per-frame evaluation. A speedup is not evidence that the 4K/30 target passed.

## Matched local measurement on 2026-10-20

RTX 5090, Torch 2.9.1+cu130, optional Ultralytics 8.4.182; YOLO26 Nano FP16 at 392 (rounded to 416), 512-side optical flow, CPU IMAGE input, two 1920x1080 frames, 2x Quality SR plus NR to 3840x2160. Both modes use identical source fingerprints and the same input checksum. Each has a separately recorded cold request, one warmup and three measured samples.

| Measurement | Isolated | Persistent NR |
|---|---:|---:|
| Median seconds / two source frames | 35.081 | 25.787 |
| Empirical range, seconds | 33.134–37.507 | 22.755–29.211 |
| Source FPS | 0.0570 | 0.0776 |
| Median inclusive NR stage, seconds | 16.898 | 9.624 |
| 4K output above 30 source FPS | FAIL | FAIL |

Observed complete-node throughput improved **1.36x** in this short-batch comparison. These are three sequential, unpaired samples per mode; unchanged SR timing also varied (medians 14.345 versus 11.230 seconds), so do not attribute the entire pipeline difference to NR initialization or extrapolate to long clips. Native processing and its CPU/file transfers still dominate. The target remains unmet.

Records: [isolated](benchmarks/2026-10-20-native-isolated.json), [persistent NR](benchmarks/2026-10-20-native-persistent.json), [verification](benchmarks/2026-10-20-native-verification.md). Loading/decoding, queue wait and saving/encoding are excluded.
