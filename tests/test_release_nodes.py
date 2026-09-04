from pathlib import Path
import importlib.util

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_nodes", ROOT / "nodes.py")
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)


def test_persistent_mode_is_one_native_window():
    assert list(nodes._pipeline_windows(241, 8, 8, "Persistent full sequence")) == [(0, 241)]


def test_overlap_add_keeps_length_and_crossfades():
    old = torch.zeros(6, 1, 1, 1)
    new = torch.ones(6, 1, 1, 1)
    merged = nodes._overlap_add(old, new, 4)
    assert merged.shape[0] == 8
    assert merged[2].item() == 0.0
    assert merged[5].item() == 1.0


def test_raft_pairs_are_current_to_previous():
    frames = torch.arange(5).view(5, 1, 1, 1)
    current, previous = nodes._raft_frame_pairs(frames, 1, 4)
    assert current.flatten().tolist() == [1, 2, 3]
    assert previous.flatten().tolist() == [0, 1, 2]


def test_chunked_guides_write_memory_maps(tmp_path):
    depth = torch.rand(5, 2, 3, 3)
    motion = torch.full((5, 2, 3, 3), 0.5)
    dp, mp = tmp_path / "depth.npy", tmp_path / "motion.npy"
    nodes._save_guides_chunked(depth, motion, (4, 6), dp, mp, chunk_size=2)
    assert np.load(dp, mmap_mode="r").shape == (5, 4, 6)
    assert np.load(mp, mmap_mode="r").shape == (5, 4, 6, 2)


def test_temporal_video_depth_nodes_are_registered():
    assert nodes.NODE_CLASS_MAPPINGS["DLSS5VideoDepthAnything"] is nodes.DLSS5VideoDepthAnything
    assert nodes.NODE_CLASS_MAPPINGS["DLSS5FlashDepth"] is nodes.DLSS5FlashDepth


def test_dlss_frame_generation_nodes_are_registered():
    assert nodes.NODE_CLASS_MAPPINGS["DLSSFrameGeneration"] is nodes.DLSSFrameGeneration
    assert (
        nodes.NODE_CLASS_MAPPINGS["DLSSFrameGenerationStatus"]
        is nodes.DLSSFrameGenerationStatus
    )


def test_dlssg_workflow_uses_native_widgets_not_legacy_widget_sockets():
    import json

    workflow = json.loads(
        (ROOT / "workflows" / "06_video_dlssg_24_to_48.json").read_text(
            encoding="utf-8"
        )
    )
    frame_generation = next(
        node for node in workflow["nodes"] if node["type"] == "DLSSFrameGeneration"
    )
    assert [entry["name"] for entry in frame_generation["inputs"]] == [
        "images",
        "motion_vectors",
    ]
    assert frame_generation["widgets_values"] == [
        "2x",
        24.0,
        0.28,
        "Fail on missing frames (recommended)",
    ]


def test_dlssg_motion_guide_decodes_to_pixel_units():
    motion = torch.full((1, 2, 4, 3), 0.5)
    motion[..., 0] = 0.75
    motion[..., 1] = 0.25
    decoded = nodes._dlssg_motion_pixels(motion, (2, 4))
    assert decoded.shape == (1, 2, 4, 2)
    assert np.all(decoded[..., 0] == 2.0)
    assert np.all(decoded[..., 1] == -1.0)


def test_dlssg_scene_cut_detection_marks_first_and_large_change():
    images = torch.zeros(3, 2, 2, 3)
    images[2] = 1.0
    assert nodes._dlssg_scene_resets(images, 0.5) == [True, False, True]


def test_dlssg_node_interleaves_generated_frames(monkeypatch, tmp_path):
    worker = tmp_path / "dlssg-worker.exe"
    runtime = tmp_path / "nvngx_dlssg.dll"
    worker.touch()
    runtime.touch()
    monkeypatch.setattr(nodes, "_dlssg_runtime_paths", lambda: (worker, runtime))

    class FakeSession:
        maximum = 3

        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def process_frame(self, rgba, motion, *_args, reset):
            if reset:
                return []
            middle = np.full_like(rgba, 128)
            middle[..., 3] = 255
            return [middle]

        def log_text(self):
            return ""

    monkeypatch.setattr(nodes, "DLSSGSession", FakeSession)
    images = torch.stack((torch.zeros(2, 2, 3), torch.full((2, 2, 3), 0.8)))
    motion = torch.full_like(images, 0.5)
    result, fps, report = nodes.DLSSFrameGeneration().generate(
        images, motion, "2x", 24.0, 1.0
    )
    assert result.shape == (3, 2, 2, 3)
    assert torch.all(result[0] == 0)
    assert torch.allclose(result[1], torch.full_like(result[1], 128 / 255))
    assert torch.allclose(result[2], torch.full_like(result[2], 204 / 255))
    assert fps == 48.0
    assert "2 input frames -> 3 output frames" in report


def test_vda_exposes_blackwell_compatible_attention_size():
    sizes = nodes.DLSS5VideoDepthAnything.INPUT_TYPES()["required"]["input_size"][0]
    assert sizes == ["280 (compatible)", "392 (fast)", "518 (best)"]


def test_runtime_config_is_optional(monkeypatch, tmp_path):
    monkeypatch.setattr(nodes, "PACKAGE", tmp_path)
    assert nodes._runtime_config() == {}


def test_easy_presets_cover_quality_and_memory_scenarios():
    still = nodes._easy_preset("Still image")
    long_video = nodes._easy_preset("Long video / memory efficient")
    preview = nodes._easy_preset("Fast preview")

    assert still["processing_mode"] == "Persistent full sequence"
    assert long_video["processing_mode"] == "Bounded overlap-add"
    assert long_video["flow_model"].startswith("RAFT Small")
    assert preview["flow_model"] == "Optical Flow (fastest)"
    assert nodes._easy_preset("Auto (recommended)", 1) == still
    assert nodes._easy_preset("Auto (recommended)", 240) == long_video


def test_runtime_setup_check_creates_and_reports_drop_location(monkeypatch, tmp_path):
    monkeypatch.setattr(nodes, "PACKAGE", tmp_path)
    report = nodes.DLSS5RuntimeSetup().run("Check location", False)[0]
    assert (tmp_path / "runtime").is_dir()
    assert (tmp_path / "runtime" / "dlssg").is_dir()
    assert "nvngx_dlssnr.dll" in report
    assert "dlssg-worker.exe" in report
    assert "MISSING" in report


def test_dlssg_disabled_interval_preserves_duration(monkeypatch, tmp_path):
    worker = tmp_path / "dlssg-worker.exe"
    runtime = tmp_path / "nvngx_dlssg.dll"
    worker.touch()
    runtime.touch()
    monkeypatch.setattr(nodes, "_dlssg_runtime_paths", lambda: (worker, runtime))

    class DisabledSession:
        maximum = 1

        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def process_frame(self, _rgba, _motion, *_args, reset):
            return []

        def log_text(self):
            return ""

    monkeypatch.setattr(nodes, "DLSSGSession", DisabledSession)
    images = torch.stack((torch.zeros(2, 2, 3), torch.full((2, 2, 3), 0.8)))
    motion = torch.full_like(images, 0.5)
    result, fps, report = nodes.DLSSFrameGeneration().generate(
        images, motion, "2x", 24.0, 1.0, "Hold previous frame"
    )
    assert result.shape[0] == 3
    assert torch.all(result[1] == 0)
    assert fps == 48.0
    assert "disabled_intervals=1" in report


def test_dlssg_missing_frames_fail_by_default(monkeypatch, tmp_path):
    worker = tmp_path / "dlssg-worker.exe"
    runtime = tmp_path / "nvngx_dlssg.dll"
    worker.touch()
    runtime.touch()
    monkeypatch.setattr(nodes, "_dlssg_runtime_paths", lambda: (worker, runtime))

    class DisabledSession:
        maximum = 3

        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def process_frame(self, _rgba, _motion, *_args, reset):
            return []

        def log_text(self):
            return ""

    monkeypatch.setattr(nodes, "DLSSGSession", DisabledSession)
    images = torch.stack((torch.zeros(2, 2, 3), torch.full((2, 2, 3), 0.8)))
    motion = torch.full_like(images, 0.5)
    with pytest.raises(RuntimeError, match="Try 2x"):
        nodes.DLSSFrameGeneration().generate(images, motion, "4x", 24.0, 1.0)
