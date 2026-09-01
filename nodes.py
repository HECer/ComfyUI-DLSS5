from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import torch
import torch.nn.functional as F


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
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _runtime_timeout():
    value = int(
        os.environ.get("DLSS5_TIMEOUT", _runtime_config().get("timeout_seconds", 0))
    )
    return value or None


def _first_existing(candidates: list[Path]) -> Path | None:
    return next((path for path in candidates if path.is_file()), None)


def _runtime_paths() -> tuple[Path, Path, Path]:
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
        if path is None
    ]
    if missing:
        raise RuntimeError("DLSS 5 runtime missing: " + ", ".join(missing))
    return python, plugin, snippet


def _sr_runtime_paths() -> tuple[Path, Path, Path]:
    config = _runtime_config()
    python_value = os.environ.get("DLSS5_PYTHON") or config.get("python")
    python = _first_existing(
        ([Path(python_value)] if python_value else [])
        + [
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
        if p is None
    ]
    if missing:
        raise RuntimeError(
            "DLSS Super Resolution runtime missing: " + ", ".join(missing)
        )
    return python, plugin, runtime


class DLSSSuperResolution:
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
                "image": ("IMAGE",),
                "depth": ("IMAGE",),
                "motion_vectors": ("IMAGE",),
                "scale": (["2x", "3x", "4x"],),
                "quality": (list(cls.QUALITY),),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "upscale"
    CATEGORY = "image/NVIDIA DLSS 5"

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
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "depth": ("IMAGE",),
                "motion_vectors": ("IMAGE",),
                "scale": (["2x", "3x", "4x"],),
                "sr_quality": (list(DLSSSuperResolution.QUALITY),),
                "processing_mode": (
                    ["Persistent full sequence", "Bounded overlap-add"],
                ),
                "chunk_size": ("INT", {"default": 8, "min": 2, "max": 64}),
                "history_overlap": ("INT", {"default": 8, "min": 0, "max": 32}),
                "style": (["0 - neutral", "1", "2"],),
                "style_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
                "local_structure": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0}),
                "skin_structure": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 2.0}),
                "auto_mask": ("BOOLEAN", {"default": True}),
                "depth_inverted": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "run"
    CATEGORY = "image/NVIDIA DLSS 5"

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
                "1x",
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
                "image": ("IMAGE",),
                "scenario": (cls.SCENARIOS,),
                "operation": (
                    [
                        "Upscale + neural rendering",
                        "Upscale only",
                        "Neural rendering only",
                    ],
                ),
                "scale": (["2x", "3x", "4x"],),
                "quality": (
                    ["Quality", "Balanced", "Performance", "Ultra Performance"],
                ),
                "look": (list(cls.LOOKS),),
                "effect_strength": (
                    "FLOAT",
                    {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "run"
    CATEGORY = "image/Experimental DLSS Bridge"

    def run(self, image, scenario, operation, scale, quality, look, effect_strength):
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
                "1x",
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
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "style": (["0 - neutral", "1", "2"],),
                "style_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "local_structure": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01},
                ),
                "skin_structure": (
                    "FLOAT",
                    {"default": -1.0, "min": -1.0, "max": 2.0, "step": 0.01},
                ),
                "auto_mask": ("BOOLEAN", {"default": True}),
                "pre_scale": (["1x", "2x", "4x"],),
                "depth_inverted": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "effect_mask": ("MASK",),
                "depth": ("IMAGE",),
                "motion_vectors": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "runtime_report")
    FUNCTION = "render"
    CATEGORY = "image/NVIDIA DLSS 5"

    def render(
        self,
        image,
        style,
        style_strength,
        intensity,
        local_structure,
        skin_structure,
        auto_mask,
        pre_scale,
        depth_inverted,
        effect_mask=None,
        depth=None,
        motion_vectors=None,
    ):
        python, plugin, snippet = _runtime_paths()
        source = image.detach().to(device="cpu", dtype=torch.float32)
        factor = int(pre_scale[0])
        if factor != 1:
            source = F.interpolate(
                source.permute(0, 3, 1, 2),
                scale_factor=factor,
                mode="bicubic",
                align_corners=False,
                antialias=True,
            ).permute(0, 2, 3, 1)
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

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "pyramid_scale": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.1, "max": 0.9, "step": 0.05},
                ),
                "levels": ("INT", {"default": 5, "min": 1, "max": 8}),
                "window_size": ("INT", {"default": 21, "min": 5, "max": 51, "step": 2}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("motion_vectors",)
    FUNCTION = "estimate"
    CATEGORY = "image/NVIDIA DLSS 5/guides"

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
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "model": (["RAFT Large (best)", "RAFT Small (fast)"],),
                "chunk_size": ("INT", {"default": 2, "min": 1, "max": 16}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("motion_vectors",)
    FUNCTION = "estimate"
    CATEGORY = "image/NVIDIA DLSS 5/guides"

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

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("IMAGE",),
                "motion_vectors": ("IMAGE",),
                "strength": (
                    "FLOAT",
                    {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "disocclusion_threshold": (
                    "FLOAT",
                    {"default": 0.08, "min": 0.001, "max": 1.0, "step": 0.001},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("depth",)
    FUNCTION = "stabilize"
    CATEGORY = "image/NVIDIA DLSS 5/guides"

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
    MODELS = {
        "Small (recommended)": "depth-anything/Depth-Anything-V2-Small-hf",
        "Base": "depth-anything/Depth-Anything-V2-Base-hf",
        "Large": "depth-anything/Depth-Anything-V2-Large-hf",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "model": (list(cls.MODELS),),
                "temporal_normalization": ("BOOLEAN", {"default": True}),
                "chunk_size": ("INT", {"default": 4, "min": 1, "max": 32}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("depth",)
    FUNCTION = "estimate"
    CATEGORY = "image/NVIDIA DLSS 5/guides"

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


class DLSS5RuntimeStatus:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "status"
    CATEGORY = "image/NVIDIA DLSS 5"

    def status(self):
        try:
            nr_python, nr_plugin, nr_runtime = _runtime_paths()
            sr_python, sr_plugin, sr_runtime = _sr_runtime_paths()
            return (
                f"READY\nVapourSynth Python: {nr_python}\n"
                f"NR wrapper: {nr_plugin}\nNR runtime: {nr_runtime}\n"
                f"SR wrapper: {sr_plugin}\nSR runtime: {sr_runtime}\n"
                f"Shared Python: {nr_python == sr_python}",
            )
        except Exception as exc:
            return (f"NOT READY\n{exc}",)


class DLSS5RuntimeSetup:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "action": (["Check location", "Install verified VapourKit"],),
                "confirm_download": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("setup_report",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "image/Experimental DLSS Bridge/setup"

    def run(self, action, confirm_download):
        runtime_dir = PACKAGE / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        neural_runtime = runtime_dir / "nvngx_dlssnr.dll"
        if action == "Check location":
            state = "FOUND" if neural_runtime.is_file() else "MISSING"
            return (
                f"Neural runtime: {state}\nCopy nvngx_dlssnr.dll to:\n{neural_runtime}\n\n"
                "Then select 'Install verified VapourKit', enable confirm_download, and queue this node again.",
            )
        if not confirm_download:
            return (
                "Download not started. Enable confirm_download after reviewing the pinned source in the README.",
            )
        from .install_runtime import install

        return (install(),)


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
    "DLSS5TemporalDepthStabilize": DLSS5TemporalDepthStabilize,
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
    "DLSS5TemporalDepthStabilize": "DLSS 5 Temporal Depth Stabilizer",
}
