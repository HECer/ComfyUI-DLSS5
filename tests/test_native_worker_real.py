"""Opt-in native numerical equivalence; requires the configured NVIDIA bridge."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("DLSS5_NATIVE_TESTS") != "1",
                                reason="Set DLSS5_NATIVE_TESTS=1 with a real configured native bridge")


def test_real_nr_worker_matches_isolated_across_inputs_and_invalidation(tmp_path):
    spec = importlib.util.spec_from_file_location("native_real_nodes", ROOT / "nodes.py")
    nodes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nodes)
    width, height = (3840, 2160) if os.environ.get("DLSS5_NATIVE_TEST_SIZE") == "4k" else (768, 432)
    ramp = torch.linspace(0, 1, width)[None, :, None]
    a = ramp.expand(height, -1, 3).clone()
    a[:, :, 1] = torch.linspace(0, 1, height)[:, None]
    a = torch.stack((a, torch.roll(a, 7, 1)))
    b = (1 - torch.roll(a, 31, 2)).flip(-1).contiguous()
    guide_a, guide_b = a[..., :1].expand(-1, -1, -1, 3), b[..., :1].expand(-1, -1, -1, 3)
    motion_a = torch.full_like(a, .5)
    motion_b = motion_a.clone()
    motion_b[..., 0] += .001
    cases = [("A", a, guide_a, motion_a, .85), ("B", b, guide_b, motion_b, .85),
             ("A_again", a, guide_a, motion_a, .85),
             ("still", b[:1], guide_b[:1], motion_b[:1], .85),
             ("after_still", a, guide_a, motion_a, .85),
             ("settings", a, guide_a, motion_a, .65),
             ("shape", b[:, ::2, ::2], guide_b[:, ::2, ::2], motion_b[:, ::2, ::2], .65)]
    records, references = [], {}
    def render(image, depth, motion, intensity, mode):
        return nodes.DLSS5NeuralRendering().render(
            image, "0 - neutral", .595, intensity, 1., -1., True, True,
            depth=depth, motion_vectors=motion, native_mode=mode)
    try:
        # Capture isolated references first: no persistent GPU workload overlaps them.
        for label, image, depth, motion, intensity in cases:
            reference, _ = render(image, depth, motion, intensity, nodes.NATIVE_MODES[0])
            path = tmp_path / (label + ".npy")
            np.save(path, reference.numpy())
            references[label] = path
        for label, image, depth, motion, intensity in cases:
            started = time.perf_counter()
            actual, report = render(image, depth, motion, intensity, nodes.NATIVE_MODES[1])
            expected = np.load(references[label], mmap_mode="r")
            max_error = float(np.max(np.abs(actual.numpy() - expected)))
            record = {"case": label, "shape": list(actual.shape), "max_abs_error": max_error,
                      "seconds": time.perf_counter() - started, "report": report}
            records.append(record)
            print(json.dumps(record), flush=True)
            assert actual.shape == expected.shape
            np.testing.assert_array_equal(actual.numpy(), expected)
            assert ("initialization=reused" in report) == (label in ("B", "A_again", "still", "after_still"))
    finally:
        nodes._NATIVE_MODULE.close_workers()
        evidence = {"cases": records, "source_fingerprint": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("nodes.py", "bridge_runner.py", "native_session.py", "native_worker.py")}}
        output = os.environ.get("DLSS5_NATIVE_EVIDENCE")
        if output:
            Path(output).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
