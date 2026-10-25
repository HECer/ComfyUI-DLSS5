"""Optional YOLO26 depth inference; never installs dependencies into ComfyUI."""
from pathlib import Path
import os

import numpy as np
import torch
import torch.nn.functional as F


_YOLO_CACHE = {}


def infer_yolo_depth(images, variant, input_size, precision, chunk_size,
                     temporal_normalization, engine_path="", check_cancel=None, progress=None):
    if variant not in ("nano", "small"):
        raise ValueError("Unknown YOLO26 depth variant.")
    if chunk_size < 1 or input_size < 0 or images.shape[0] < 1:
        raise ValueError("Depth inference needs frames, a positive chunk size and a nonnegative input size.")
    device = images.device if images.device.type == "cuda" else torch.device(
        "cuda" if torch.cuda.is_available() else "cpu")
    half = precision == "FP16" and device.type == "cuda"
    engine = Path(engine_path.strip()).expanduser() if engine_path.strip() else None
    if engine is not None:
        if engine.suffix.lower() != ".engine" or not engine.is_file():
            raise ValueError("TensorRT engine_path must name an existing .engine file.")
        if device.type != "cuda":
            raise ValueError("TensorRT depth engines require CUDA.")
    # Ultralytics can otherwise run pip from checkpoint/backend loaders. Disable
    # both first-import and already-imported paths for this host process.
    os.environ["YOLO_AUTOINSTALL"] = "false"
    try:
        from ultralytics import YOLO, utils
        from ultralytics.models.yolo.depth import DepthPredictor  # noqa: F401
        from ultralytics.utils import checks
    except ImportError as exc:
        raise RuntimeError(
            "YOLO26 requires an Ultralytics release with depth support. The package is missing "
            "or too old. See docs/FAST_DEPTH.md for optional setup; ComfyUI's Torch is not changed."
        ) from exc
    utils.AUTOINSTALL = False
    checks.AUTOINSTALL = False
    if engine is None:
        try:
            import folder_paths
            root = Path(folder_paths.models_dir)
        except ImportError:
            root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        root = root / "dlss5" / "yolo26"
        root.mkdir(parents=True, exist_ok=True)
        checkpoint = root / ("yolo26n-depth.pt" if variant == "nano" else "yolo26s-depth.pt")
    else:
        checkpoint = engine.resolve()
    key = (str(checkpoint), str(device), half)
    if key not in _YOLO_CACHE:
        if check_cancel:
            check_cancel()
        _YOLO_CACHE[key] = YOLO(str(checkpoint), task="depth")
    model = _YOLO_CACHE[key]
    size = ((input_size or 768) + 31) // 32 * 32
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(images), chunk_size):
            if check_cancel:
                check_cancel()
            frames = images[start:start + chunk_size].detach().permute(0, 3, 1, 2).to(device).float()
            if engine is None and max(frames.shape[2:]) > size:
                scale = size / max(frames.shape[2:])
                target = tuple(max(1, round(d * scale)) for d in frames.shape[2:])
                # perf: bound host preprocessing by model input size, not source size.
                # See tools/benchmark_fast_depth.py; the full-resolution path spent time in clip/copies.
                frames = F.interpolate(frames, size=target, mode="bilinear", align_corners=False)
            frames = frames.clamp(0, 1).mul(255).round().byte().permute(0, 2, 3, 1).cpu().numpy()
            # Ultralytics NumPy inputs are BGR; ComfyUI IMAGE tensors are RGB.
            source = [np.ascontiguousarray(frame[..., ::-1]) for frame in frames]
            results = model.predict(source=source, imgsz=size, device=str(device), half=half,
                                    verbose=False, save=False)
            if len(results) != len(source):
                raise RuntimeError("YOLO26 depth returned a different frame count.")
            batch = []
            for result in results:
                metric = getattr(getattr(result, "depth", None), "data", None)
                if metric is None or metric.shape != frames.shape[1:3]:
                    raise RuntimeError("YOLO26 depth did not return an aligned depth map.")
                metric = metric.detach().float()
                if not torch.isfinite(metric).all() or (metric <= 0).any():
                    raise RuntimeError("YOLO26 depth contains invalid metric depth values.")
                # Existing DLSS guides use inverse depth: near surfaces are bright.
                batch.append(metric)
            metric = torch.stack(batch)
            if metric.shape[1:3] != images.shape[1:3]:
                metric = F.interpolate(metric[:, None], size=images.shape[1:3],
                                       mode="bilinear", align_corners=False)[:, 0]
            chunks.append(metric.reciprocal().cpu())
            if progress:
                progress(min(start + chunk_size, len(images)))
    if temporal_normalization:
        samples = [chunk[:, ::8, ::8].flatten() if min(chunk.shape[1:]) >= 16 else chunk.flatten()
                   for chunk in chunks]
        sample = torch.cat(samples).to(device)
        low, high = torch.quantile(sample, torch.tensor([0.02, 0.98], device=device))
        del sample, samples
    output = []
    for chunk in chunks:
        if check_cancel:
            check_cancel()
        depth = chunk.to(device)
        if not temporal_normalization:
            low = torch.quantile(depth.flatten(1), 0.02, dim=1)[:, None, None]
            high = torch.quantile(depth.flatten(1), 0.98, dim=1)[:, None, None]
        depth = ((depth - low) / (high - low).clamp_min(1e-6)).clamp(0, 1)
        output.append(depth.to(images.device))
    return torch.cat(output)[..., None].expand(-1, -1, -1, 3)
