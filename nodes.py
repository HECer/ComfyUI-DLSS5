from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from fractions import Fraction

import numpy as np
import torch
import torch.nn.functional as F

try:
    from .dlssg_backend import DLSSGSession, hags_enabled, probe_worker
except ImportError:
    import importlib.util

    _DLSSG_SPEC = importlib.util.spec_from_file_location(
        "dlssg_backend", Path(__file__).resolve().with_name("dlssg_backend.py")
    )
    _DLSSG_MODULE = importlib.util.module_from_spec(_DLSSG_SPEC)
    _DLSSG_SPEC.loader.exec_module(_DLSSG_MODULE)
    DLSSGSession = _DLSSG_MODULE.DLSSGSession
    hags_enabled = _DLSSG_MODULE.hags_enabled
    probe_worker = _DLSSG_MODULE.probe_worker


PACKAGE = Path(__file__).resolve().parent
PROJECT = PACKAGE.parent
_DEPTH_CACHE = {}
_RAFT_CACHE = {}


def _iter_temporal_chunks(frame_count: int, chunk_size: int, history_overlap: int):
    """Yield native input start/stop and the number of warm-up frames to discard."""
    for output_start in range(0, frame_count, chunk_size):
        stop = min(output_start + chunk_size, frame_count)
        warm_start = max(0, output_start - history_overlap)
        yield warm_start, stop, output_start - warm_start


def _raft_frame_pairs(source: torch.Tensor, start: int, stop: int):
    """Return current/previous pairs for current-to-previous reprojection vectors."""
    return source[start:stop], source[start - 1 : stop - 1]


def _iter_overlap_windows(frame_count: int, chunk_size: int, overlap: int):
    for start in range(0, frame_count, chunk_size):
        yield start, min(frame_count, start + chunk_size + overlap)


def _pipeline_windows(
    frame_count: int, chunk_size: int, overlap: int, processing_mode: str
):
    if processing_mode == "Persistent full sequence":
        yield 0, frame_count
    else:
        yield from _iter_overlap_windows(frame_count, chunk_size, overlap)


def _easy_preset(scenario: str, frame_count: int | None = None):
    if scenario == "Auto (recommended)":
        if frame_count is None:
            raise ValueError("frame_count is required for the Auto preset")
        scenario = (
            "Still image"
            if frame_count == 1
            else (
                "Short video / best quality"
                if frame_count <= 96
                else "Long video / memory efficient"
            )
        )
    presets = {
        "Still image": dict(
            flow_model="Optical Flow (fastest)",
            flow_chunk=1,
            processing_mode="Persistent full sequence",
            chunk_size=2,
            overlap=0,
        ),
        "Short video / best quality": dict(
            flow_model="RAFT Large (best)",
            flow_chunk=2,
            processing_mode="Persistent full sequence",
            chunk_size=8,
            overlap=8,
        ),
        "Long video / memory efficient": dict(
            flow_model="RAFT Small (fast)",
            flow_chunk=4,
            processing_mode="Bounded overlap-add",
            chunk_size=16,
            overlap=8,
        ),
        "Fast preview": dict(
            flow_model="Optical Flow (fastest)",
            flow_chunk=8,
            processing_mode="Bounded overlap-add",
            chunk_size=8,
            overlap=2,
        ),
    }
    return presets[scenario]


def _overlap_add(previous: torch.Tensor, current: torch.Tensor, overlap: int):
    shared = min(overlap, len(previous), len(current))
    if shared <= 0:
        return torch.cat((previous, current), dim=0)
    phase = torch.linspace(
        0.0, torch.pi, shared, device=previous.device, dtype=previous.dtype
    )
    weight = (0.5 - 0.5 * torch.cos(phase)).view(shared, *([1] * (previous.ndim - 1)))
    blend = previous[-shared:] * (1.0 - weight) + current[:shared] * weight
    return torch.cat((previous[:-shared], blend, current[shared:]), dim=0)


def _save_guides_chunked(
    depth, motion_vectors, size, depth_path, motion_path, chunk_size=4
):
    count = depth.shape[0]
    height, width = size
    depth_file = np.lib.format.open_memmap(
        depth_path, mode="w+", dtype=np.float32, shape=(count, height, width)
    )
    motion_file = np.lib.format.open_memmap(
        motion_path, mode="w+", dtype=np.float32, shape=(count, height, width, 2)
    )
    for start in range(0, count, chunk_size):
        stop = min(start + chunk_size, count)
        d = F.interpolate(
            depth[start:stop].detach().cpu().float().permute(0, 3, 1, 2),
            size=size,
            mode="bilinear",
            align_corners=False,
        )[:, 0]
        mv = F.interpolate(
            motion_vectors[start:stop].detach().cpu().float().permute(0, 3, 1, 2),
            size=size,
            mode="bilinear",
            align_corners=False,
        )[:, :2]
        mv = (mv - 0.5) * 2.0
        mv[:, 0] *= width
        mv[:, 1] *= height
        depth_file[start:stop] = d.numpy()
        motion_file[start:stop] = mv.permute(0, 2, 3, 1).numpy()
    depth_file.flush()
    motion_file.flush()


def _runtime_temp_dir() -> Path:
    configured = _runtime_config().get("temp_dir")
    path = Path(
        os.environ.get(
            "DLSS5_TEMP_DIR",
            configured or (Path(tempfile.gettempdir()) / "comfyui-dlss5"),
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_config() -> dict:
    path = PACKAGE / "runtime" / "config.json"
    if not path.is_file():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid runtime configuration at {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"Invalid runtime configuration at {path}: expected a JSON object")
    return config


def _runtime_timeout():
    value = int(
        os.environ.get("DLSS5_TIMEOUT", _runtime_config().get("timeout_seconds", 0))
    )
    return value or None


def _first_existing(candidates: list[Path]) -> Path | None:
    return next((path for path in candidates if path.is_file()), None)


def _runtime_paths(check_files=True) -> tuple[Path, Path, Path]:
    config = _runtime_config()
    python_value = os.environ.get("DLSS5_PYTHON") or config.get("python")
    python = Path(python_value) if python_value else None
    if python is None:
        python = _first_existing(
            [
                PROJECT / "test-env" / "Scripts" / "python.exe",
                Path(os.sys.executable),
            ]
        )
    plugin = _first_existing(
        [
            Path(os.environ["DLSS5_PLUGIN"])
            if os.environ.get("DLSS5_PLUGIN")
            else Path("__missing__"),
            Path(config["nr_plugin"])
            if config.get("nr_plugin")
            else Path("__missing__"),
            PROJECT
            / "third_party"
            / "vapourkit-src"
            / "native"
            / "vsdlssnr"
            / "build"
            / "vsdlssnr.dll",
            PROJECT
            / "test-env"
            / "Lib"
            / "site-packages"
            / "vapoursynth"
            / "plugins"
            / "vsdlssnr.dll",
            PACKAGE / "runtime" / "vsdlssnr.dll",
        ]
    )
    snippet = _first_existing(
        [
            Path(os.environ["DLSS5_SNIPPET"])
            if os.environ.get("DLSS5_SNIPPET")
            else Path("__missing__"),
            Path(config["nr_runtime"])
            if config.get("nr_runtime")
            else Path("__missing__"),
            PROJECT / "nvngx_dlssnr.dll",
            PROJECT
            / "test-env"
            / "Lib"
            / "site-packages"
            / "vapoursynth"
            / "plugins"
            / "nvngx_dlssnr.dll",
            PACKAGE / "runtime" / "nvngx_dlssnr.dll",
        ]
    )
    missing = [
        name
        for name, path in (
            ("Python", python),
            ("vsdlssnr.dll", plugin),
            ("nvngx_dlssnr.dll", snippet),
        )
        if _runtime_file_status(path) != "PRESENT"
    ]
    if check_files and missing:
        raise RuntimeError("DLSS 5 runtime missing: " + ", ".join(missing))
    return python, plugin, snippet


def _sr_runtime_paths(check_files=True) -> tuple[Path, Path, Path]:
    config = _runtime_config()
    python_value = os.environ.get("DLSS5_PYTHON") or config.get("python")
    python = Path(python_value) if python_value else _first_existing(
        [
            PROJECT / "test-env" / "Scripts" / "python.exe",
            Path(os.sys.executable),
        ]
    )
    plugin = _first_existing(
        [
            Path(os.environ["DLSS5_SR_PLUGIN"])
            if os.environ.get("DLSS5_SR_PLUGIN")
            else Path("__missing__"),
            Path(config["sr_plugin"])
            if config.get("sr_plugin")
            else Path("__missing__"),
            PROJECT
            / "third_party"
            / "vapourkit-src"
            / "native"
            / "vsdlsssr"
            / "build"
            / "vsdlsssr.dll",
            PROJECT
            / "test-env"
            / "Lib"
            / "site-packages"
            / "vapoursynth"
            / "plugins"
            / "vsdlsssr.dll",
            PACKAGE / "runtime" / "vsdlsssr.dll",
        ]
    )
    runtime = _first_existing(
        [
            Path(os.environ["DLSS5_SR_RUNTIME"])
            if os.environ.get("DLSS5_SR_RUNTIME")
            else Path("__missing__"),
            Path(config["sr_runtime"])
            if config.get("sr_runtime")
            else Path("__missing__"),
            PROJECT
            / "third_party"
            / "NVIDIA-DLSS"
            / "lib"
            / "Windows_x86_64"
            / "rel"
            / "nvngx_dlss.dll",
            PROJECT
            / "test-env"
            / "Lib"
            / "site-packages"
            / "vapoursynth"
            / "plugins"
            / "nvngx_dlss.dll",
            PACKAGE / "runtime" / "nvngx_dlss.dll",
        ]
    )
    missing = [
        n
        for n, p in (
            ("Python", python),
            ("vsdlsssr.dll", plugin),
            ("nvngx_dlss.dll", runtime),
        )
        if _runtime_file_status(p) != "PRESENT"
    ]
    if check_files and missing:
        raise RuntimeError(
            "DLSS Super Resolution runtime missing: " + ", ".join(missing)
        )
    return python, plugin, runtime


def _runtime_file_status(path):
    if path is None or not path.is_file():
        return "MISSING"
    try:
        with path.open("rb") as stream:
            prefix = stream.read(128)
    except OSError:
        return "UNREADABLE"
    if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
        return "LFS POINTER"
    return "PRESENT"


def _runtime_probe(python, script, *arguments):
    try:
        result = subprocess.run(
            [str(python), "-c", script + "\nprint('DLSS_PROBE_OK')", *map(str, arguments)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False, "timed out after 10 seconds"
    except OSError as exc:
        return False, f"launch failed: {exc}"
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()[-1000:]
        return False, f"failed (exit {result.returncode}): {detail}"
    if "DLSS_PROBE_OK" not in result.stdout.splitlines():
        return False, "failed: executable did not complete the Python probe"
    return True, "PASS"


def _bridge_diagnostics(stages=("sr", "nr")):
    lines = ["DLSS bridge diagnostics (local paths)", "Inference: UNTESTED (no GPU inference performed)"]
    try:
        paths = {
            stage: (_sr_runtime_paths(False) if stage == "sr" else _runtime_paths(False))
            for stage in stages
        }
    except RuntimeError as exc:
        return False, "\n".join(lines + [str(exc)])
    python = next(iter(paths.values()))[0]
    python_state = _runtime_file_status(python)
    lines.append(f"Python file: {python_state} ({python})")
    files_ok = {}
    for stage, (_, plugin, runtime) in paths.items():
        states = [_runtime_file_status(plugin), _runtime_file_status(runtime)]
        files_ok[stage] = all(state == "PRESENT" for state in states)
        for label, path, state in zip(("wrapper", "runtime"), (plugin, runtime), states):
            lines.append(f"{stage.upper()} {label} file: {state} ({path})")
    if any("LFS POINTER" in line for line in lines):
        lines.append("Fetch the actual binaries with git lfs pull in the extension repository.")
    if python_state != "PRESENT" or not all(files_ok.values()):
        lines.append("Repair missing/unreadable files or correct runtime/config.json and DLSS5 environment overrides.")
    repair = (
        f"Repair the selected interpreter ({python}); verify it imports vapoursynth and numpy. "
        "For missing NumPy, run that interpreter with -m pip install numpy==2.5.2. "
        "Alternatively use Runtime Setup > Install verified VapourKit to configure the automatic runtime; "
        "it does not repair an external VapourKit interpreter."
    )
    if python_state == "PRESENT":
        python_ok, detail = _runtime_probe(python, "import sys; print(sys.version)")
        lines.append("Python: " + (detail if python_ok else f"FAIL: {detail}"))
    else:
        python_ok = False
        lines.append("Python: FAIL: selected executable is missing or unusable")
    imports_ok = python_ok
    for label, module in (("VapourSynth", "vapoursynth"), ("NumPy", "numpy")):
        if python_ok:
            passed, detail = _runtime_probe(python, f"import {module}; print({module}.__version__)")
            imports_ok &= passed
            lines.append(f"{label} import: " + (detail if passed else f"FAIL: {detail}"))
        else:
            lines.append(f"{label} import: SKIPPED (Python failed)")
    if not imports_ok:
        lines.append(repair)
    plugins_ok = True
    loaded = []
    for stage, (_, plugin, _) in paths.items():
        if not imports_ok or not files_ok[stage]:
            plugins_ok = False
            lines.append(f"{stage.upper()} plugin load: SKIPPED (required files/imports failed)")
            continue
        script = "import sys; import vapoursynth as vs\n"
        for index, name in enumerate([*loaded, stage], 1):
            function = "Upscale" if name == "sr" else "Enhance"
            script += f"vs.core.std.LoadPlugin(path=sys.argv[{index}])\nassert callable(vs.core.dlss{name}.{function})\n"
        passed, detail = _runtime_probe(python, script, *(paths[name][1] for name in [*loaded, stage]))
        plugins_ok &= passed
        lines.append(f"{stage.upper()} plugin load: " + (detail if passed else f"FAIL: {detail}"))
        if passed:
            loaded.append(stage)
        else:
            lines.append("Check the configured wrapper, VapourSynth ABI and its dependent DLLs; reinstall the verified bridge if needed.")
    passed = imports_ok and plugins_ok and all(files_ok.values())
    lines.append("Preflight: " + ("PASS; inference remains untested" if passed else "FAIL"))
    return passed, "\n".join(lines)


def _text_result(report):
    return {"ui": {"text": [report]}, "result": (report,)}


def _dlssg_runtime_paths() -> tuple[Path, Path]:
    config = _runtime_config()
    worker_value = os.environ.get("DLSS5_DLSSG_WORKER") or config.get("dlssg_worker")
    runtime_value = os.environ.get("DLSS5_DLSSG_RUNTIME") or config.get("dlssg_runtime")
    worker = _first_existing(
        ([Path(worker_value)] if worker_value else [])
        + [PACKAGE / "runtime" / "dlssg" / "dlssg-worker.exe"]
    )
    runtime = _first_existing(
        ([Path(runtime_value)] if runtime_value else [])
        + [PACKAGE / "runtime" / "dlssg" / "nvngx_dlssg.dll"]
    )
    missing = [
        name
        for name, path in (("dlssg-worker.exe", worker), ("nvngx_dlssg.dll", runtime))
        if path is None
    ]
    if missing:
        raise RuntimeError(
            "DLSS Frame Generation runtime missing: "
            + ", ".join(missing)
            + f". Place both files in {PACKAGE / 'runtime' / 'dlssg'}"
        )
    if worker.parent.resolve() != runtime.parent.resolve():
        raise RuntimeError("dlssg-worker.exe and nvngx_dlssg.dll must share one directory")
    return worker, runtime


def _dlssg_motion_pixels(motion_vectors: torch.Tensor, size: tuple[int, int]) -> np.ndarray:
    height, width = size
    motion = F.interpolate(
        motion_vectors.detach().cpu().float().permute(0, 3, 1, 2)[:, :2],
        size=size,
        mode="bilinear",
        align_corners=False,
    )
    motion = (motion - 0.5) * 2.0
    motion[:, 0] *= width
    motion[:, 1] *= height
    return motion.permute(0, 2, 3, 1).numpy().astype(np.float16, copy=False)


def _dlssg_scene_resets(images: torch.Tensor, threshold: float) -> list[bool]:
    source = images.detach().cpu().float()
    resets = [True]
    for index in range(1, len(source)):
        score = torch.mean(torch.abs(source[index] - source[index - 1])).item()
        resets.append(score >= threshold)
    return resets


class DLSSFrameGeneration:
    DESCRIPTION = "Experimental external DLSS Frame Generation for a sequence. Supply current-to-previous motion vectors encoded around 0.5; install its optional worker before use."
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input image sequence; Frame Generation requires at least two frames."}),
                "motion_vectors": ("IMAGE", {"tooltip": "Current-to-previous motion encoded in RGB around 0.5, with horizontal and vertical components scaled to pixels."}),
                "multiplier": (["2x", "3x", "4x"], {"tooltip": "Number of output frames per input interval; higher multipliers need more generated frames."}),
                "input_fps": (
                    "FLOAT",
                    {"default": 24.0, "min": 1.0, "max": 240.0, "step": 0.001, "tooltip": "Source frame rate used to report the multiplied output frame rate."},
                ),
                "scene_cut_threshold": (
                    "FLOAT",
                    {"default": 0.28, "min": 0.01, "max": 1.0, "step": 0.01, "tooltip": "Detects scene changes and avoids interpolation across a cut."},
                ),
                "runtime_fallback": (
                    ["Fail on missing frames (recommended)", "Hold previous frame"], {"tooltip": "Choose an explicit fallback if the experimental worker does not return every requested intermediate frame."},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "FLOAT", "STRING")
    RETURN_NAMES = ("interpolated_frames", "output_fps", "runtime_report")
    FUNCTION = "generate"
    CATEGORY = "Experimental DLSS Bridge/video"

    def generate(
        self,
        images,
        motion_vectors,
        multiplier,
        input_fps,
        scene_cut_threshold,
        runtime_fallback="Fail on missing frames (recommended)",
    ):
        if images.shape[0] < 2:
            raise ValueError("DLSS Frame Generation needs at least two input frames")
        if motion_vectors.shape[0] != images.shape[0]:
            raise ValueError("motion_vectors batch must match images")
        worker, runtime = _dlssg_runtime_paths()
        factor = int(multiplier[0])
        generated_count = factor - 1
        source = images.detach().cpu().float().clamp(0, 1)
        height, width = source.shape[1:3]
        rgba = np.empty((len(source), height, width, 4), dtype=np.uint8)
        rgba[..., :3] = np.rint(source[..., :3].numpy() * 255.0).astype(np.uint8)
        rgba[..., 3] = 255
        motion = _dlssg_motion_pixels(motion_vectors, (height, width))
        resets = _dlssg_scene_resets(source, float(scene_cut_threshold))
        output = []
        disabled_frames = 0
        reset_fill_frames = 0
        frame_rate = Fraction(str(float(input_fps))).limit_denominator(1_000_000)
        with DLSSGSession(
            worker,
            runtime.parent,
            width,
            height,
            len(source),
            generated_count,
        ) as session:
            for index in range(len(source)):
                generated = session.process_frame(
                    rgba[index],
                    motion[index],
                    index * frame_rate.denominator,
                    frame_rate.numerator,
                    reset=resets[index],
                )
                if index == 0:
                    output.append(rgba[index, ..., :3])
                    continue
                if resets[index]:
                    generated = [rgba[index - 1]] * generated_count
                    reset_fill_frames += generated_count
                if len(generated) != generated_count and not resets[index]:
                    disabled_frames += 1
                    if runtime_fallback.startswith("Fail"):
                        raise RuntimeError(
                            f"DLSS-G returned {len(generated)} of {generated_count} "
                            f"requested frame(s) at source frame {index}. Try 2x, enable "
                            "HAGS, or select 'Hold previous frame' explicitly."
                        )
                    generated = list(generated[:generated_count])
                    generated.extend(
                        [rgba[index - 1]] * (generated_count - len(generated))
                    )
                output.extend(frame[..., :3] for frame in generated)
                output.append(rgba[index, ..., :3])
            maximum = session.maximum
            logs = session.log_text()
        result = torch.from_numpy(np.stack(output).astype(np.float32) / 255.0)
        output_fps = float(input_fps) * factor
        report = (
            f"NVIDIA DLSS Frame Generation; {len(source)} input frames -> "
            f"{len(result)} output frames; requested={factor}x; output_fps={output_fps:g}; "
            f"scene_resets={sum(resets) - 1}; runtime_max={maximum + 1}x; "
            f"reset_fill_frames={reset_fill_frames}; disabled_intervals={disabled_frames}; "
            f"worker={worker}; runtime={runtime}"
        )
        if logs:
            report += "\nWorker log:\n" + logs
        return result.to(images.device), output_fps, report


class DLSSFrameGenerationStatus:
    DESCRIPTION = "Checks whether the optional experimental Frame Generation worker, runtime, and HAGS requirement are ready."
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "status"
    CATEGORY = "Experimental DLSS Bridge/video"

    def status(self):
        try:
            worker, runtime = _dlssg_runtime_paths()
            result = probe_worker(worker, runtime.parent)
            hags = hags_enabled()
            readiness = "READY" if hags is not False else "READY (HAGS WARNING)"
            return (
                readiness + "\n"
                f"Worker: {worker}\nRuntime: {runtime}\nHAGS: {hags}\n"
                + json.dumps(result, indent=2),
            )
        except Exception as exc:
            return (f"NOT READY\n{exc}",)


class DLSSSuperResolution:
    DESCRIPTION = "Experimental bridge to NVIDIA DLSS Super Resolution. Depth and motion_vectors are paired guides and must describe the same input frames."
    QUALITY = {
        "Quality": 2,
        "Balanced": 1,
        "Performance": 0,
        "Ultra Performance": 3,
        "Ultra Quality": 4,
        "DLAA": 5,
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image or frame sequence to upscale."}),
                "depth": ("IMAGE", {"tooltip": "Depth guide paired with motion_vectors for the same input frames."}),
                "motion_vectors": ("IMAGE", {"tooltip": "Current-to-previous motion guide paired with depth; encoded around 0.5 in pixel-relative RGB values."}),
                "scale": (["2x", "3x", "4x"], {"tooltip": "Grows output width and height by this factor, so 2x creates four times as many pixels."}),
                "quality": (list(cls.QUALITY), {"tooltip": "DLSS quality preset; DLAA selects anti-aliasing, while scale still controls output dimensions."}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "upscale"
    CATEGORY = "Experimental DLSS Bridge/advanced"

    def upscale(self, image, depth, motion_vectors, scale, quality="Quality"):
        python, plugin, _runtime = _sr_runtime_paths()
        factor = int(scale[0])
        source = image.detach().cpu().float()
        if (
            depth.shape[0] != source.shape[0]
            or motion_vectors.shape[0] != source.shape[0]
        ):
            raise ValueError("depth and motion_vectors batch must match image")
        size = source.shape[1:3]
        d = F.interpolate(
            depth.detach().cpu().float().permute(0, 3, 1, 2),
            size=size,
            mode="bilinear",
            align_corners=False,
        )[:, 0]
        mv = F.interpolate(
            motion_vectors.detach().cpu().float().permute(0, 3, 1, 2),
            size=size,
            mode="bilinear",
            align_corners=False,
        )[:, :2]
        mv = (mv - 0.5) * 2.0
        mv[:, 0] *= size[1]
        mv[:, 1] *= size[0]
        with tempfile.TemporaryDirectory(
            prefix="comfy-dlss-sr-", dir=_runtime_temp_dir()
        ) as tmp:
            tmp = Path(tmp)
            ip = tmp / "in.npy"
            op = tmp / "out.npy"
            dp = tmp / "depth.npy"
            mp = tmp / "mvec.npy"
            np.save(ip, source.numpy())
            np.save(dp, d.numpy())
            np.save(mp, mv.permute(0, 2, 3, 1).numpy())
            cmd = [
                str(python),
                str(PACKAGE / "sr_bridge_runner.py"),
                str(ip),
                str(op),
                "--depth",
                str(dp),
                "--mvec",
                str(mp),
                "--plugin",
                str(plugin),
                "--scale",
                str(factor),
                "--quality",
                str(self.QUALITY[quality]),
            ]
            p = subprocess.run(
                cmd, capture_output=True, text=True, timeout=_runtime_timeout()
            )
            if p.returncode:
                raise RuntimeError(
                    "DLSS Super Resolution failed:\n" + p.stdout + p.stderr
                )
            result = torch.from_numpy(np.load(op))
        report = f"Official NVIDIA DLSS Super Resolution; {source.shape[2]}x{source.shape[1]} -> {result.shape[2]}x{result.shape[1]}; scale={factor}x; quality={quality}; guides=depth+motion"
        return result.to(image.device), report


class DLSS5FullPipeline:
    DESCRIPTION = "Advanced experimental SR followed by Neural Rendering. Use paired depth and current-to-previous motion guides; persistent mode retains the original full-sequence behavior."
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image or frame sequence processed by SR and Neural Rendering."}),
                "depth": ("IMAGE", {"tooltip": "Depth guide paired with motion_vectors for every input frame."}),
                "motion_vectors": ("IMAGE", {"tooltip": "Current-to-previous pixel motion guide paired with depth and encoded around 0.5."}),
                "scale": (["2x", "3x", "4x"], {"tooltip": "Grows output width and height by this factor; 2x means four times the pixels."}),
                "sr_quality": (list(DLSSSuperResolution.QUALITY), {"tooltip": "DLSS Super Resolution quality preset."}),
                "processing_mode": (
                    ["Persistent full sequence", "Bounded overlap-add"], {"tooltip": "Persistent processes the whole sequence; bounded overlap-add limits memory while retaining overlap context."},
                ),
                "chunk_size": ("INT", {"default": 8, "min": 2, "max": 64, "tooltip": "Frames per bounded processing window; ignored by Persistent full sequence."}),
                "history_overlap": ("INT", {"default": 8, "min": 0, "max": 32, "tooltip": "Prior frames repeated for bounded windows; ignored by Persistent full sequence."}),
                "style": (["0 - neutral", "1", "2"], {"tooltip": "Neural Rendering style selection; 0 is neutral."}),
                "style_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "tooltip": "Amount of the selected Neural Rendering style."}),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "tooltip": "Overall Neural Rendering effect intensity."}),
                "local_structure": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "tooltip": "Preserves local structure during Neural Rendering."}),
                "skin_structure": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 2.0, "tooltip": "-1 delegates skin structure to the runtime; non-negative values override it."}),
                "auto_mask": ("BOOLEAN", {"default": True, "tooltip": "Lets the runtime generate a mask when no explicit effect mask is used."}),
                "depth_inverted": ("BOOLEAN", {"default": False, "tooltip": "Enable only when the supplied depth guide uses the opposite near/far convention."}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "run"
    CATEGORY = "Experimental DLSS Bridge/advanced"

    def run(
        self,
        image,
        depth,
        motion_vectors,
        scale,
        sr_quality,
        processing_mode,
        chunk_size,
        history_overlap,
        style,
        style_strength,
        intensity,
        local_structure,
        skin_structure,
        auto_mask,
        depth_inverted,
    ):
        output = None
        reports = []
        for start, stop in _pipeline_windows(
            image.shape[0], chunk_size, history_overlap, processing_mode
        ):
            sl = slice(start, stop)
            up, sr = DLSSSuperResolution().upscale(
                image[sl], depth[sl], motion_vectors[sl], scale, sr_quality
            )
            out, nr = DLSS5NeuralRendering().render(
                up,
                style,
                style_strength,
                intensity,
                local_structure,
                skin_structure,
                auto_mask,
                depth_inverted,
                depth=depth[sl],
                motion_vectors=motion_vectors[sl],
            )
            output = (
                out if output is None else _overlap_add(output, out, history_overlap)
            )
            reports.append(
                f"frames {start}-{stop - 1}: mode={processing_mode}; overlap={history_overlap}; {sr} | {nr}"
            )
        return output[: image.shape[0]], "\n".join(reports)


class DLSS5EasyPipeline:
    """Opinionated one-node path; advanced nodes remain available for authored guides."""
    DESCRIPTION = "Experimental one-node DLSS path. Scenario selects bounded processing, currently limited to Upscale + neural rendering; quality is ignored for Neural rendering only, and scale is ignored when no upscaling operation is selected."

    SCENARIOS = [
        "Auto (recommended)",
        "Still image",
        "Short video / best quality",
        "Long video / memory efficient",
        "Fast preview",
    ]
    LOOKS = {
        "Neutral / faithful": ("0 - neutral", 0.70, 1.00, -1.00),
        "Realistic detail": ("2", 0.85, 1.20, 0.10),
        "Strong detail": ("2", 1.00, 1.45, 0.30),
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image or frame sequence; Auto selects a preset from its frame count."}),
                "scenario": (cls.SCENARIOS, {"tooltip": "Chooses the Easy processing preset and whether a sequence is bounded for memory."}),
                "operation": (
                    [
                        "Upscale + neural rendering",
                        "Upscale only",
                        "Neural rendering only",
                    ], {"tooltip": "Choose SR plus rendering, SR alone, or Neural Rendering alone. Scale and quality are ignored for Neural Rendering only."},
                ),
                "scale": (["2x", "3x", "4x"], {"tooltip": "Grows output width and height; ignored for Neural Rendering only."}),
                "quality": (
                    ["Quality", "Balanced", "Performance", "Ultra Performance"], {"tooltip": "Super Resolution quality preset; ignored for Neural Rendering only."},
                ),
                "look": (list(cls.LOOKS), {"tooltip": "Easy Neural Rendering look; this preset sets style and structure controls, and is ignored for Upscale only."}),
                "effect_strength": (
                    "FLOAT",
                    {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Blends the selected Easy look; ignored for Upscale only."},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "run"
    CATEGORY = "Experimental DLSS Bridge"

    def run(self, image, scenario, operation, scale, quality, look, effect_strength):
        stages = {
            "Upscale only": ("sr",),
            "Neural rendering only": ("nr",),
            "Upscale + neural rendering": ("sr", "nr"),
        }[operation]
        passed, diagnostic = _bridge_diagnostics(stages)
        if not passed:
            raise RuntimeError("DLSS Easy preflight failed:\n" + diagnostic)
        preset = _easy_preset(scenario, int(image.shape[0]))
        depth = DLSS5DepthAnythingV2().estimate(image, "Small (recommended)", True, 4)[
            0
        ]
        if preset["flow_model"] == "Optical Flow (fastest)":
            motion = DLSS5OpticalFlow().estimate(image, 0.5, 5, 21)[0]
        else:
            motion = DLSS5RAFTFlow().estimate(
                image, preset["flow_model"], preset["flow_chunk"]
            )[0]
        if image.shape[0] > 1:
            depth = DLSS5TemporalDepthStabilize().stabilize(depth, motion, 0.7, 0.08)[0]
        style, base_strength, local_structure, skin_structure = self.LOOKS[look]
        if operation == "Upscale only":
            output, report = DLSSSuperResolution().upscale(
                image, depth, motion, scale, quality
            )
        elif operation == "Neural rendering only":
            output, report = DLSS5NeuralRendering().render(
                image,
                style,
                base_strength * effect_strength,
                effect_strength,
                local_structure,
                skin_structure,
                True,
                True,
                depth=depth,
                motion_vectors=motion,
            )
        else:
            output, report = DLSS5FullPipeline().run(
                image,
                depth,
                motion,
                scale,
                quality,
                preset["processing_mode"],
                preset["chunk_size"],
                preset["overlap"],
                style,
                base_strength * effect_strength,
                effect_strength,
                local_structure,
                skin_structure,
                True,
                True,
            )
        summary = (
            f"Easy preset: {scenario}; guide={preset['flow_model']}; "
            f"operation={operation}; mode={preset['processing_mode']}; look={look}\n"
        )
        return output, summary + report


class DLSS5NeuralRendering:
    DESCRIPTION = "Experimental DLSS Neural Rendering. Connect both depth and motion_vectors together for temporal guidance; skin -1 delegates to the runtime, and first use may download the required model."
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image or frame sequence for Neural Rendering."}),
                "style": (["0 - neutral", "1", "2"], {"tooltip": "Neural Rendering style; 0 is the neutral baseline."}),
                "style_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Amount of the selected style."},
                ),
                "intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Overall Neural Rendering effect intensity."},
                ),
                "local_structure": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Local structure preservation strength."},
                ),
                "skin_structure": (
                    "FLOAT",
                    {"default": -1.0, "min": -1.0, "max": 2.0, "step": 0.01, "tooltip": "-1 delegates skin structure to the runtime; non-negative values override it."},
                ),
                "auto_mask": ("BOOLEAN", {"default": True, "tooltip": "Requests automatic runtime masking independently of effect_mask; any supplied effect mask limits the final image afterward."}),
                "depth_inverted": ("BOOLEAN", {"default": False, "tooltip": "Enable only if the supplied depth guide is near/far inverted."}),
            },
            "optional": {
                "effect_mask": ("MASK", {"tooltip": "Optional mask that limits Neural Rendering to selected image areas."}),
                "depth": ("IMAGE", {"tooltip": "Optional depth guide; connect it only together with motion_vectors."}),
                "motion_vectors": ("IMAGE", {"tooltip": "Optional current-to-previous motion guide; connect it only together with depth."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "render"
    CATEGORY = "Experimental DLSS Bridge/advanced"

    def render(
        self,
        image,
        style,
        style_strength,
        intensity,
        local_structure,
        skin_structure,
        auto_mask,
        depth_inverted,
        effect_mask=None,
        depth=None,
        motion_vectors=None,
    ):
        python, plugin, snippet = _runtime_paths()
        source = image.detach().to(device="cpu", dtype=torch.float32)
        settings = {
            "style": int(style.split()[0]),
            "style_strength": style_strength,
            "intensity": intensity,
            "local_structure": local_structure,
            "skin_structure": skin_structure,
            "auto_mask": bool(auto_mask),
            "feature_id": 18,
            "preset": 0,
            "depth_inverted": bool(depth_inverted),
        }
        if (depth is None) != (motion_vectors is None):
            raise ValueError("depth and motion_vectors must be connected together")
        with tempfile.TemporaryDirectory(
            prefix="comfy-dlss5-", dir=_runtime_temp_dir()
        ) as tmp:
            input_path, output_path = Path(tmp) / "in.npy", Path(tmp) / "out.npy"
            np.save(input_path, source.numpy())
            command = [
                str(python),
                str(PACKAGE / "bridge_runner.py"),
                str(input_path),
                str(output_path),
                "--plugin",
                str(plugin),
                "--snippet",
                str(snippet),
                "--settings",
                json.dumps(settings),
            ]
            if depth is not None:
                guide_size = source.shape[1:3]
                depth_path, motion_path = (
                    Path(tmp) / "depth.npy",
                    Path(tmp) / "mvec.npy",
                )
                _save_guides_chunked(
                    depth, motion_vectors, guide_size, depth_path, motion_path
                )
                command += ["--depth", str(depth_path), "--mvec", str(motion_path)]
            process = subprocess.run(
                command, capture_output=True, text=True, timeout=_runtime_timeout()
            )
            if process.returncode:
                raise RuntimeError("DLSS 5 failed:\n" + process.stdout + process.stderr)
            result = torch.from_numpy(np.load(output_path))
        if effect_mask is not None:
            mask = effect_mask.detach().to(device="cpu", dtype=torch.float32)
            if mask.ndim == 2:
                mask = mask[None]
            mask = F.interpolate(
                mask[:, None],
                size=result.shape[1:3],
                mode="bilinear",
                align_corners=False,
            )
            if mask.shape[0] == 1 and result.shape[0] > 1:
                mask = mask.expand(result.shape[0], -1, -1, -1)
            mask = mask.permute(0, 2, 3, 1).clamp(0, 1)
            result = source * (1 - mask) + result * mask
        report = (
            f"DLSS-NR 310.8 Feature 18; {result.shape[2]}x{result.shape[1]}; "
            f"{result.shape[0]} frame(s); temporal={'yes' if result.shape[0] > 1 else 'still-baseline'}; "
            f"guides={'depth+motion' if depth is not None else 'none'}"
        )
        return (result.to(image.device), report)


class DLSS5OpticalFlow:
    """Generate dense current-to-previous pixel motion, encoded as a Comfy IMAGE."""
    DESCRIPTION = "Fast optical-flow guide for experimental DLSS nodes. It produces current-to-previous pixel motion in RGB, encoded around 0.5."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input frame sequence used to estimate current-to-previous motion."}),
                "pyramid_scale": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.1, "max": 0.9, "step": 0.05, "tooltip": "Image-pyramid downscale for the fast optical-flow estimator."},
                ),
                "levels": ("INT", {"default": 5, "min": 1, "max": 8, "tooltip": "Number of optical-flow pyramid levels."}),
                "window_size": ("INT", {"default": 21, "min": 5, "max": 51, "step": 2, "tooltip": "Pixel neighborhood used by the optical-flow solver."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("motion_vectors",)
    FUNCTION = "estimate"
    CATEGORY = "Experimental DLSS Bridge/guides"

    def estimate(self, images, pyramid_scale, levels, window_size):
        import cv2

        array = images.detach().cpu().float().numpy()
        count, height, width, _ = array.shape
        encoded = np.full((count, height, width, 3), 0.5, dtype=np.float32)
        previous = None
        for index in range(count):
            gray = cv2.cvtColor(
                np.clip(array[index] * 255, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY
            )
            if previous is not None:
                # Match the current-to-previous convention used by RAFT and reprojection.
                flow = cv2.calcOpticalFlowFarneback(
                    gray,
                    previous,
                    None,
                    pyramid_scale,
                    int(levels),
                    int(window_size),
                    3,
                    5,
                    1.2,
                    0,
                )
                encoded[index, :, :, 0] = np.clip(
                    0.5 + flow[:, :, 0] / (2 * width), 0, 1
                )
                encoded[index, :, :, 1] = np.clip(
                    0.5 + flow[:, :, 1] / (2 * height), 0, 1
                )
            previous = gray
        return (torch.from_numpy(encoded).to(images.device),)


class DLSS5RAFTFlow:
    DESCRIPTION = "Higher-quality RAFT motion guide for experimental DLSS nodes. It downloads the selected RAFT weights on first use and encodes current-to-previous pixel motion around 0.5."
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input frame sequence used to estimate current-to-previous motion."}),
                "model": (["RAFT Large (best)", "RAFT Small (fast)"], {"tooltip": "RAFT weight set; the selected model downloads on first use."}),
                "chunk_size": ("INT", {"default": 2, "min": 1, "max": 16, "tooltip": "Number of frame pairs inferred together; reduce it if memory is limited."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("motion_vectors",)
    FUNCTION = "estimate"
    CATEGORY = "Experimental DLSS Bridge/guides"

    def estimate(self, images, model, chunk_size):
        from torchvision.models.optical_flow import (
            raft_large,
            raft_small,
            Raft_Large_Weights,
            Raft_Small_Weights,
        )

        device = (
            images.device
            if images.device.type == "cuda"
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        key = (model, str(device))
        if key not in _RAFT_CACHE:
            weights = (
                Raft_Large_Weights.DEFAULT
                if model.startswith("RAFT Large")
                else Raft_Small_Weights.DEFAULT
            )
            network = (raft_large if model.startswith("RAFT Large") else raft_small)(
                weights=weights, progress=True
            )
            _RAFT_CACHE[key] = (network.eval().to(device), weights.transforms())
        network, transform = _RAFT_CACHE[key]
        source = images.detach().cpu().permute(0, 3, 1, 2).float()
        count, _, height, width = source.shape
        padded_h = max(128, ((height + 7) // 8) * 8)
        padded_w = max(128, ((width + 7) // 8) * 8)
        encoded = torch.full((count, height, width, 3), 0.5, device="cpu")
        with torch.inference_mode():
            for start in range(1, count, chunk_size):
                stop = min(start + chunk_size, count)
                current, previous = _raft_frame_pairs(source, start, stop)
                current = F.interpolate(
                    current,
                    size=(padded_h, padded_w),
                    mode="bilinear",
                    align_corners=False,
                ).to(device)
                previous = F.interpolate(
                    previous,
                    size=(padded_h, padded_w),
                    mode="bilinear",
                    align_corners=False,
                ).to(device)
                current, previous = transform(current, previous)
                flow = network(current, previous)[-1]
                flow = F.interpolate(
                    flow, size=(height, width), mode="bilinear", align_corners=False
                )
                flow[:, 0] *= width / padded_w
                flow[:, 1] *= height / padded_h
                encoded[start:stop, :, :, 0] = (
                    (0.5 + flow[:, 0] / (2 * width)).clamp(0, 1).cpu()
                )
                encoded[start:stop, :, :, 1] = (
                    (0.5 + flow[:, 1] / (2 * height)).clamp(0, 1).cpu()
                )
                del current, previous, flow
        return (encoded.to(images.device),)


class DLSS5TemporalDepthStabilize:
    """Reproject the prior stabilized depth with current-to-previous motion."""
    DESCRIPTION = "Stabilizes a depth sequence by reprojection with current-to-previous motion. Use matching frames and the same 0.5-centered motion encoding used by the guide nodes."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("IMAGE", {"tooltip": "Depth sequence to stabilize temporally."}),
                "motion_vectors": ("IMAGE", {"tooltip": "Matching current-to-previous motion encoded around 0.5 in pixel-relative channels."}),
                "strength": (
                    "FLOAT",
                    {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Blend strength for reprojected prior depth."},
                ),
                "disocclusion_threshold": (
                    "FLOAT",
                    {"default": 0.08, "min": 0.001, "max": 1.0, "step": 0.001, "tooltip": "Depth difference at which reprojection confidence falls for disocclusions."},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("depth",)
    FUNCTION = "stabilize"
    CATEGORY = "Experimental DLSS Bridge/guides"

    def stabilize(self, depth, motion_vectors, strength, disocclusion_threshold):
        if depth.shape[0] != motion_vectors.shape[0]:
            raise ValueError("depth and motion_vectors batch must match")
        source = depth.detach().cpu().float().permute(0, 3, 1, 2)[:, :1]
        motion = motion_vectors.detach().cpu().float().permute(0, 3, 1, 2)[:, :2]
        motion = F.interpolate(
            motion, size=source.shape[2:], mode="bilinear", align_corners=False
        )
        count, _, height, width = source.shape
        ys, xs = torch.meshgrid(
            torch.arange(height), torch.arange(width), indexing="ij"
        )
        base_x = xs.float()[None]
        base_y = ys.float()[None]
        stabilized = [source[0]]
        for index in range(1, count):
            flow_x = (motion[index : index + 1, 0] - 0.5) * 2.0 * width
            flow_y = (motion[index : index + 1, 1] - 0.5) * 2.0 * height
            grid_x = 2.0 * (base_x + flow_x) / max(width - 1, 1) - 1.0
            grid_y = 2.0 * (base_y + flow_y) / max(height - 1, 1) - 1.0
            grid = torch.stack((grid_x, grid_y), dim=-1)
            previous = stabilized[-1][None]
            warped = F.grid_sample(
                previous,
                grid,
                mode="bilinear",
                padding_mode="border",
                align_corners=True,
            )[0]
            current = source[index]
            confidence = torch.exp(
                -torch.abs(current - warped) / max(disocclusion_threshold, 1e-6)
            )
            blend = float(strength) * confidence
            stabilized.append(current * (1.0 - blend) + warped * blend)
        result = (
            torch.stack(stabilized)
            .permute(0, 2, 3, 1)
            .expand(-1, -1, -1, 3)
            .contiguous()
        )
        return (result.to(depth.device),)


class DLSS5DepthAnythingV2:
    DESCRIPTION = "Depth Anything V2 guide for experimental DLSS nodes. The selected model downloads on first use; keep temporal normalization for a stable sequence-wide depth range."
    MODELS = {
        "Small (recommended)": "depth-anything/Depth-Anything-V2-Small-hf",
        "Base": "depth-anything/Depth-Anything-V2-Base-hf",
        "Large": "depth-anything/Depth-Anything-V2-Large-hf",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input image or sequence used for depth estimation."}),
                "model": (list(cls.MODELS), {"tooltip": "Depth Anything V2 model; its weights download on first use."}),
                "temporal_normalization": ("BOOLEAN", {"default": True, "tooltip": "Uses one depth range across the sequence to reduce temporal flicker."}),
                "chunk_size": ("INT", {"default": 4, "min": 1, "max": 32, "tooltip": "Frames estimated together; reduce it when memory is limited."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("depth",)
    FUNCTION = "estimate"
    CATEGORY = "Experimental DLSS Bridge/guides"

    def estimate(self, images, model, temporal_normalization, chunk_size):
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        model_id = self.MODELS[model]
        device = (
            images.device
            if images.device.type == "cuda"
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        key = (model_id, str(device))
        if key not in _DEPTH_CACHE:
            processor = AutoImageProcessor.from_pretrained(model_id)
            network = (
                AutoModelForDepthEstimation.from_pretrained(model_id).eval().to(device)
            )
            _DEPTH_CACHE[key] = (processor, network)
        processor, network = _DEPTH_CACHE[key]
        source = images.detach().cpu().float()
        chunks = []
        with torch.inference_mode():
            for start in range(0, source.shape[0], chunk_size):
                frames = source[start : start + chunk_size]
                inputs = processor(
                    images=[
                        np.rint(frame.numpy().clip(0, 1) * 255).astype(np.uint8)
                        for frame in frames
                    ],
                    return_tensors="pt",
                )
                inputs = {name: value.to(device) for name, value in inputs.items()}
                part = network(**inputs).predicted_depth[:, None]
                part = F.interpolate(
                    part, size=source.shape[1:3], mode="bicubic", align_corners=False
                )[:, 0]
                chunks.append(part.cpu())
                del inputs, part
        depth = torch.cat(chunks, dim=0)
        if temporal_normalization:
            sample = depth[:, ::8, ::8].flatten()
            low, high = torch.quantile(sample, torch.tensor([0.02, 0.98]))
            depth = (depth - low) / (high - low).clamp_min(1e-6)
        else:
            flat = depth.flatten(1)
            low = torch.quantile(flat, 0.02, dim=1)[:, None, None]
            high = torch.quantile(flat, 0.98, dim=1)[:, None, None]
            depth = (depth - low) / (high - low).clamp_min(1e-6)
        depth = depth.clamp(0, 1)[..., None].expand(-1, -1, -1, 3)
        return (depth.to(images.device),)


class DLSS5VideoDepthAnything:
    """Temporally consistent depth using the official Apache-2.0 VDA-S model."""
    DESCRIPTION = "Video Depth Anything Small creates temporally consistent depth guides for experimental DLSS workflows. The VDA-S model downloads on first use."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input frame sequence used for VDA-S depth estimation."}),
                "input_size": (["280 (compatible)", "392 (fast)", "518 (best)"], {"tooltip": "VDA-S inference size; larger sizes favor detail while using more memory."}),
                "precision": (["FP16 (recommended)", "FP32"], {"tooltip": "Inference precision; FP32 is slower and uses more memory."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("temporally_consistent_depth",)
    FUNCTION = "estimate"
    CATEGORY = "Experimental DLSS Bridge/guides"

    def estimate(self, images, input_size, precision):
        from .video_depth_backend import infer_vda_small

        size = int(input_size.split()[0])
        depth = infer_vda_small(images, input_size=size, fp32=precision == "FP32")
        return (depth,)


class DLSS5FlashDepth:
    """High-resolution FlashDepth through a conflict-free external environment."""
    DESCRIPTION = "Optional high-resolution FlashDepth guide through a separate environment. It is experimental and may download its selected model on first use."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Input frame sequence sent to the separate FlashDepth environment."}),
                "variant": (["FlashDepth-L (low resolution)", "FlashDepth Full (2K)"], {"tooltip": "FlashDepth model variant; its assets may download on first use."}),
                "flashdepth_python": ("STRING", {"default": "", "tooltip": "Required path to the isolated FlashDepth environment Python executable; blank values fail validation."}),
                "flashdepth_repository": ("STRING", {"default": "", "tooltip": "Required path to the FlashDepth checkout containing train.py; blank values fail validation."}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 240.0, "tooltip": "Frame rate passed to FlashDepth for temporal processing."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("temporally_consistent_depth",)
    FUNCTION = "estimate"
    CATEGORY = "Experimental DLSS Bridge/guides/optional"

    def estimate(self, images, variant, flashdepth_python, flashdepth_repository, fps):
        from .video_depth_backend import infer_flashdepth_external

        return (infer_flashdepth_external(images, variant, flashdepth_python, flashdepth_repository, fps),)


class DLSS5RuntimeStatus:
    DESCRIPTION = "Read-only file, Python, NumPy, VapourSynth and plugin-load diagnostics. Each isolated probe has a 10-second timeout. GPU inference is not tested. Reports contain local paths."
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "status"
    CATEGORY = "Experimental DLSS Bridge/setup"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls):
        return float("nan")

    def status(self):
        return _text_result(_bridge_diagnostics()[1])


class DLSS5RuntimeSetup:
    DESCRIPTION = "One-click setup for the experimental DLSS bridge. Downloads occur only after confirmation; Frame Generation is optional and installed separately."
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "action": ([
                    "Check location",
                    "Install verified VapourKit",
                    "Install verified Frame Generation",
                ], {"tooltip": "Check readiness, install the verified bridge, or install optional Frame Generation separately."}),
                "confirm_download": ("BOOLEAN", {"default": False, "tooltip": "Required before any verified download starts; Check location does not download."}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("setup_report",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "Experimental DLSS Bridge/setup"

    @classmethod
    def IS_CHANGED(cls, action, confirm_download):
        return float("nan")

    def run(self, action, confirm_download):
        runtime_dir = PACKAGE / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        frame_generation_dir = runtime_dir / "dlssg"
        frame_generation_dir.mkdir(parents=True, exist_ok=True)
        neural_runtime = runtime_dir / "nvngx_dlssnr.dll"
        sr_runtime = runtime_dir / "nvngx_dlss.dll"
        dlssg_runtime = frame_generation_dir / "nvngx_dlssg.dll"
        bundled_wrappers = (runtime_dir / "vsdlssnr.dll", runtime_dir / "vsdlsssr.dll")
        wrapper_states = [_runtime_file_status(path) for path in bundled_wrappers]
        wrapper_state = "PRESENT" if all(state == "PRESENT" for state in wrapper_states) else ", ".join(wrapper_states)
        if action == "Check location":
            neural_state = _runtime_file_status(neural_runtime)
            sr_state = _runtime_file_status(sr_runtime)
            dlssg_state = _runtime_file_status(dlssg_runtime)
            return _text_result(
                f"Bundled NVIDIA SR runtime: {sr_state}\n{sr_runtime}\n"
                f"Bundled NVIDIA NR runtime: {neural_state}\n{neural_runtime}\n\n"
                f"Bundled VapourSynth wrappers: {wrapper_state}\n"
                f"Expected: {bundled_wrappers[0].name}, {bundled_wrappers[1].name}\n\n"
                "Optional Frame Generation files belong together in:\n"
                f"{frame_generation_dir}\n"
                f"Bundled NVIDIA FG runtime: {dlssg_state}\n"
                f"Expected runtime: {dlssg_runtime.name}; worker: dlssg-worker.exe\n\n"
                "File presence does not verify runtime operation. Run DLSS 5 Runtime Status for bounded dependency/plugin probes.\n"
                "For LFS POINTER files, run git lfs pull in the extension repository.\n"
                "To configure the automatic runtime, select 'Install verified VapourKit', enable confirm_download, and queue this node again.",
            )
        if not confirm_download:
            return _text_result(
                "Download not started. Enable confirm_download after reviewing the pinned source in the README.",
            )
        from .install_runtime import install, install_frame_generation

        if action == "Install verified Frame Generation":
            return _text_result(install_frame_generation())
        return _text_result(install())


NODE_CLASS_MAPPINGS = {
    "DLSS5RuntimeSetup": DLSS5RuntimeSetup,
    "DLSS5EasyPipeline": DLSS5EasyPipeline,
    "DLSSSuperResolution": DLSSSuperResolution,
    "DLSS5FullPipeline": DLSS5FullPipeline,
    "DLSS5NeuralRendering": DLSS5NeuralRendering,
    "DLSS5RuntimeStatus": DLSS5RuntimeStatus,
    "DLSS5OpticalFlow": DLSS5OpticalFlow,
    "DLSS5RAFTFlow": DLSS5RAFTFlow,
    "DLSS5DepthAnythingV2": DLSS5DepthAnythingV2,
    "DLSS5VideoDepthAnything": DLSS5VideoDepthAnything,
    "DLSS5FlashDepth": DLSS5FlashDepth,
    "DLSS5TemporalDepthStabilize": DLSS5TemporalDepthStabilize,
    "DLSSFrameGeneration": DLSSFrameGeneration,
    "DLSSFrameGenerationStatus": DLSSFrameGenerationStatus,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DLSS5RuntimeSetup": "DLSS Runtime Setup (One Click)",
    "DLSS5EasyPipeline": "Experimental DLSS — Easy Upscale & Render",
    "DLSSSuperResolution": "NVIDIA DLSS Super Resolution (Unofficial Bridge)",
    "DLSS5FullPipeline": "DLSS SR + Experimental Neural Rendering (Advanced)",
    "DLSS5NeuralRendering": "Experimental DLSS Neural Rendering",
    "DLSS5RuntimeStatus": "DLSS 5 Runtime Status",
    "DLSS5OpticalFlow": "DLSS 5 Optical Flow Guide",
    "DLSS5RAFTFlow": "DLSS 5 RAFT Motion Guide",
    "DLSS5DepthAnythingV2": "DLSS 5 Depth Anything V2 Guide",
    "DLSS5VideoDepthAnything": "DLSS 5 Video Depth Anything (Temporal)",
    "DLSS5FlashDepth": "DLSS 5 FlashDepth (External, Optional)",
    "DLSS5TemporalDepthStabilize": "DLSS 5 Temporal Depth Stabilizer",
    "DLSSFrameGeneration": "NVIDIA DLSS Frame Generation (External Worker)",
    "DLSSFrameGenerationStatus": "DLSS Frame Generation Runtime Status",
}
