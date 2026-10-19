"""Measure guide and full-pipeline throughput without changing installed runtimes."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

import torch


ROOT = Path(__file__).resolve().parents[1]


def synchronize():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def measure(run, warmups, repeats, sync=synchronize, clock=time.perf_counter):
    if warmups < 0 or repeats < 1:
        raise ValueError("Need nonnegative warmups and at least one measured repeat.")
    result = None
    for _ in range(warmups):
        result = run()
        sync()
    samples = []
    for _ in range(repeats):
        sync()
        start = clock()
        result = run()
        sync()
        samples.append(clock() - start)
    return samples, result


def gate_passes(samples, frames, minimum_fps, output_size=(3840, 2160)):
    return tuple(output_size) == (3840, 2160) and frames / statistics.median(samples) > minimum_fps


def summary(samples, frames):
    median = statistics.median(samples)
    return {"samples_seconds": samples, "sample_count": len(samples),
            "range_seconds": [min(samples), max(samples)], "median_seconds": median,
            "median_ms_per_source_frame": median * 1000 / frames,
            "source_fps": frames / median}


def load_nodes():
    name = "_dlss_fast_benchmark"
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py",
                                                submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return sys.modules[name + ".nodes"]


def main(argv=None):
    nodes = load_nodes()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=list(nodes.DLSS5DepthGuide.MODEL_HELP), default="Depth Anything V2 Small")
    parser.add_argument("--precision", choices=["FP16", "FP32"], default="FP16")
    parser.add_argument("--input-size", type=int, default=280)
    parser.add_argument("--motion-input-size", type=int, default=512)
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--image", type=Path, help="Repeated image with synthetic horizontal motion; no video quality claim.")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--minimum-fps", type=float, default=30.)
    parser.add_argument("--depth-only", action="store_true")
    parser.add_argument("--native-mode", choices=nodes.NATIVE_MODES, default=nodes.NATIVE_MODES[0])
    parser.add_argument("--operation", choices=nodes.DLSS5EasyPipeline.INPUT_TYPES()["required"]["operation"][0],
                        default="Upscale + neural rendering")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if min(args.frames, args.width, args.height, args.repeats) < 1 or args.warmups < 0:
        parser.error("Dimensions, frames and repeats must be positive; warmups must be nonnegative.")
    if args.input_size < 0 or args.motion_input_size < 0 or args.minimum_fps <= 0:
        parser.error("Sizes must be nonnegative and minimum FPS must be positive.")
    if args.image:
        import numpy as np
        from PIL import Image
        with Image.open(args.image) as image:
            base = torch.from_numpy(np.array(image.convert("RGB").resize((args.width, args.height)),
                                             dtype=np.float32) / 255)
        source_kind = "repeated image with synthetic motion; excludes file decoding"
    else:
        ramp = torch.linspace(0, 1, args.width)[None, :, None]
        base = ramp.expand(args.height, -1, 3).clone()
        source_kind = "synthetic gradient with horizontal motion; throughput only"
    images = torch.stack([torch.roll(base, i * 2, dims=1) for i in range(args.frames)])
    # ComfyUI normally supplies CPU IMAGE batches; preserve that boundary in measurements.
    stages = {}
    attributes = [(nodes.DLSS5DepthGuide, "estimate", "depth_guide_inclusive"),
                  (nodes.DLSS5DepthAnythingV2, "estimate", "da_v2_inclusive"),
                  (nodes.DLSS5OpticalFlow, "estimate", "motion"),
                  (nodes.DLSS5TemporalDepthStabilize, "stabilize", "stabilization"),
                  (nodes.DLSS5FullPipeline, "run", "native_pipeline_inclusive"),
                  (nodes.DLSSSuperResolution, "upscale", "native_sr"),
                  (nodes.DLSS5NeuralRendering, "render", "native_nr")]

    def instrument(original, label):
        def wrapped(*a, **kw):
            synchronize()
            start = time.perf_counter()
            result = original(*a, **kw)
            synchronize()
            stages[label] = stages.get(label, 0) + time.perf_counter() - start
            return result
        return wrapped

    def run():
        stages.clear()
        if args.depth_only:
            return nodes.DLSS5DepthGuide().estimate(images, args.model, args.input_size,
                                                   args.precision, True, 4)
        return nodes.DLSS5EasyPipeline().run(
            images, "Short video / best quality", args.operation, "2x", "Quality", "Neutral / faithful", 0.85,
            depth_model=args.model, depth_input_size=args.input_size, depth_precision=args.precision,
            motion_model="Optical Flow (fastest)", motion_input_size=args.motion_input_size,
            native_mode=args.native_mode)

    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "options": vars(args).copy(),
               "source_kind": source_kind, "source_size": [args.width, args.height],
               "source_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest() if args.image else None,
               "torch": torch.__version__, "python": sys.version,
               "gpu": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
               "source_fingerprint": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in [ROOT / name for name in ("nodes.py", "depth_backend.py", "bridge_runner.py",
                                        "sr_bridge_runner.py", "native_worker.py", "native_session.py")] + [Path(__file__)]},
               "timing_scope": "node processing with CPU IMAGE input/output; excludes load/decode, queue wait and save/encode; instrumented CUDA synchronization included; inclusive stages must not be summed"}
    try:
        with ExitStack() as stack:
            for cls, method, label in attributes:
                stack.enter_context(patch.object(cls, method, instrument(getattr(cls, method), label)))
            cold, _ = measure(run, 0, 1)
            stage_samples = []

            def measured_run():
                result = run()
                stage_samples.append(stages.copy())
                return result

            samples, (output, report) = measure(measured_run, args.warmups, args.repeats)
            measured_stages = stage_samples[args.warmups:]
        payload.update(summary(samples, args.frames))
        payload.update(cold_setup_seconds=cold[0], runtime_report=report, output_size=list(output.shape[1:3][::-1]),
                       inclusive_stage_samples_seconds=measured_stages,
                       gate="not evaluated (depth only)" if args.depth_only else (
                           "PASS" if gate_passes(samples, args.frames, args.minimum_fps,
                                                 output_size=output.shape[1:3][::-1]) else "FAIL"))
        exit_code = 0 if args.depth_only or payload["gate"] == "PASS" else 2
    except Exception as exc:
        payload.update(gate="UNVERIFIED", error=f"{type(exc).__name__}: {exc}")
        exit_code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("gate", "source_fps", "error") if key in payload}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
