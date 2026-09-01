from pathlib import Path
import importlib.util

import numpy as np
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
