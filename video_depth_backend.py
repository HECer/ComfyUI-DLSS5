"""Optional video-depth adapters. Third-party code and weights stay outside this package."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import torch

_VDA_CACHE = {}
VDA_COMMIT = "4f5ae23172ba60fd7bc11ef671cca678842c7072"
VDA_REPO = "https://github.com/DepthAnything/Video-Depth-Anything.git"


def _model_root() -> Path:
    try:
        import folder_paths

        root = Path(folder_paths.models_dir)
    except ImportError:
        root = Path(__file__).resolve().parent / "models"
    path = root / "dlss5" / "video_depth_anything"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_vda() -> tuple[Path, Path]:
    root = _model_root()
    repo = root / "source"
    checkpoint = root / "video_depth_anything_vits.pth"
    if not (repo / "video_depth_anything" / "video_depth.py").is_file():
        try:
            subprocess.run(
                ["git", "clone", "--filter=blob:none", "--no-checkout", VDA_REPO, str(repo)],
                check=True,
            )
            subprocess.run(["git", "-C", str(repo), "checkout", VDA_COMMIT], check=True)
        except Exception as exc:
            raise RuntimeError(
                "Could not install the official Video Depth Anything source. Install Git, "
                f"then retry. Destination: {repo}"
            ) from exc
    if not checkpoint.is_file():
        from huggingface_hub import hf_hub_download

        downloaded = Path(
            hf_hub_download(
                repo_id="depth-anything/Video-Depth-Anything-Small",
                filename="video_depth_anything_vits.pth",
            )
        )
        try:
            os.link(downloaded, checkpoint)
        except OSError:
            import shutil

            shutil.copy2(downloaded, checkpoint)
    return repo, checkpoint


def _normalize(depth: torch.Tensor) -> torch.Tensor:
    sample = depth[:, ::8, ::8].flatten().float()
    low, high = torch.quantile(sample, torch.tensor([0.02, 0.98]))
    return ((depth.float() - low) / (high - low).clamp_min(1e-6)).clamp(0, 1)


def infer_vda_small(images: torch.Tensor, input_size: int = 518, fp32: bool = False) -> torch.Tensor:
    repo, checkpoint = _ensure_vda()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    key = (str(checkpoint), str(device))
    if key not in _VDA_CACHE:
        sys.path.insert(0, str(repo))
        try:
            from video_depth_anything.video_depth import VideoDepthAnything
            # Some xFormers wheels import successfully but have no kernel for a
            # newly released GPU architecture. PyTorch SDPA is slower but works.
            from video_depth_anything.dinov2_layers import attention as vda_attention
            from video_depth_anything.motion_module import attention as motion_attention

            if device.type == "cuda":
                try:
                    capability = torch.cuda.get_device_capability(device)
                    if capability[0] > 9:
                        vda_attention.XFORMERS_AVAILABLE = False
                        def sdpa_forward(layer, x):
                            batch, tokens, channels = x.shape
                            qkv = layer.qkv(x).reshape(
                                batch, tokens, 3, layer.num_heads, channels // layer.num_heads
                            ).permute(2, 0, 3, 1, 4)
                            q, k, v = qkv.unbind(0)
                            result = torch.nn.functional.scaled_dot_product_attention(
                                q, k, v, dropout_p=layer.attn_drop.p if layer.training else 0.0
                            )
                            result = result.transpose(1, 2).reshape(batch, tokens, channels)
                            return layer.proj_drop(layer.proj(result))

                        vda_attention.Attention.forward = sdpa_forward

                        def temporal_sdpa(layer, query, key, value, attention_mask):
                            q = query.permute(0, 2, 1, 3)
                            k = key.permute(0, 2, 1, 3)
                            v = value.permute(0, 2, 1, 3)
                            result = torch.nn.functional.scaled_dot_product_attention(
                                q, k, v, attn_mask=attention_mask, scale=layer.scale
                            )
                            return result.permute(0, 2, 1, 3)

                        motion_attention.CrossAttention._memory_efficient_attention_split = temporal_sdpa
                except Exception:
                    pass
        finally:
            sys.path.pop(0)
        model = VideoDepthAnything(
            encoder="vits", features=64, out_channels=[48, 96, 192, 384]
        )
        model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True), strict=True)
        _VDA_CACHE[key] = model.eval().to(device)
    frames = np.rint(images.detach().cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
    depth, _ = _VDA_CACHE[key].infer_video_depth(
        frames, target_fps=24, input_size=input_size, device=device.type, fp32=fp32
    )
    result = _normalize(torch.from_numpy(depth))[..., None].expand(-1, -1, -1, 3)
    return result.to(images.device)


def _write_video(path: Path, images: torch.Tensor, fps: float) -> None:
    frames = np.rint(images.detach().cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
    height, width = frames.shape[1:3]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not create the temporary FlashDepth input video.")
    for frame in frames:
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()


def infer_flashdepth_external(images, variant, python_path, repository, fps):
    python = Path(python_path.strip())
    repo = Path(repository.strip())
    if not python.is_file() or not (repo / "train.py").is_file():
        raise RuntimeError(
            "FlashDepth is optional and must use its isolated Torch 2.4 environment. "
            "Follow docs/FLASHDEPTH.md, then set flashdepth_python and flashdepth_repository."
        )
    config = "flashdepth-l" if "-L" in variant else "flashdepth"
    with tempfile.TemporaryDirectory(prefix="comfyui-dlss5-flashdepth-") as temp:
        temp = Path(temp)
        source, output = temp / "input.mp4", temp / "output"
        _write_video(source, images, fps)
        command = [
            str(python), "-m", "torch.distributed.run", "--nproc_per_node=1",
            "train.py", "--config-path", f"configs/{config}", "inference=true",
            f"eval.random_input={source}", f"eval.outfolder={output}",
        ]
        run = subprocess.run(command, cwd=repo, text=True, capture_output=True)
        if run.returncode:
            raise RuntimeError("FlashDepth failed in its isolated environment:\n" + run.stderr[-3000:])
        candidates = sorted(output.rglob("*pred*.mp4")) + sorted(output.rglob("*depth*.mp4"))
        if not candidates:
            raise RuntimeError(f"FlashDepth completed but wrote no depth video below {output}.")
        capture, frames = cv2.VideoCapture(str(candidates[0])), []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            frames.append(gray)
        capture.release()
        if len(frames) != images.shape[0]:
            raise RuntimeError(f"FlashDepth returned {len(frames)} frames for {images.shape[0]} inputs.")
        depth = torch.from_numpy(np.stack(frames))
        return depth[..., None].expand(-1, -1, -1, 3).to(images.device)
