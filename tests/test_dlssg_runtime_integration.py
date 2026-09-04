from pathlib import Path
import importlib.util
import os

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_nodes_dlssg", ROOT / "nodes.py")
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)


@pytest.mark.skipif(
    os.environ.get("DLSS5_RUN_DLSSG_INTEGRATION") != "1",
    reason="requires the user-supplied Windows DLSS-G runtime and supported GPU",
)
def test_real_dlssg_worker_generates_complete_2x_sequence():
    height = width = 512
    x = torch.linspace(0, 1, width)[None, :, None].expand(height, width, 3)
    frames = torch.stack((x, torch.roll(x, 8, dims=1), torch.roll(x, 16, dims=1)))
    motion = torch.full_like(frames, 0.5)
    motion[1:, ..., 0] = 0.5 - 8 / (2 * width)

    output, output_fps, report = nodes.DLSSFrameGeneration().generate(
        frames, motion, "2x", 24.0, 1.0
    )

    assert output.shape == (5, height, width, 3)
    assert torch.isfinite(output).all()
    assert output_fps == 48.0
    assert "disabled_intervals=0" in report, report.split("Worker log:", 1)[0]
