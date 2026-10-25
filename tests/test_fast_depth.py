"""Offline behavioral coverage for selectable guide backends."""
import importlib.util
from pathlib import Path
import sys
import types

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nodes = load("fast_depth_nodes", "nodes.py")


def test_depth_guide_registered_and_explains_every_model():
    assert "DLSS5DepthGuide" in nodes.NODE_CLASS_MAPPINGS
    cls = nodes.NODE_CLASS_MAPPINGS["DLSS5DepthGuide"]
    for name in cls.INPUT_TYPES()["required"]["model"][0]:
        assert name in cls.MODEL_HELP
        assert len(cls.MODEL_HELP[name]) > 60


def test_guide_routes_da_options_and_reports_cpu_precision(monkeypatch):
    assert hasattr(nodes, "DLSS5DepthGuide")
    calls = []

    def estimate(self, images, model, temporal, chunk, **kwargs):
        calls.append((model, temporal, chunk, kwargs))
        return (torch.ones_like(images) * 0.4,)

    monkeypatch.setattr(nodes.DLSS5DepthAnythingV2, "estimate", estimate)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    images = torch.zeros(3, 8, 12, 3)
    depth, report = nodes.DLSS5DepthGuide().estimate(
        images, "Depth Anything V2 Small", 280, "FP16", True, 2
    )
    assert calls == [("Small (recommended)", True, 2, {"input_size": 280, "precision": "FP16"})]
    torch.testing.assert_close(depth, torch.full_like(images, 0.4))
    assert "FP32" in report and "CPU" in report and "280" in report


def test_da_explicit_size_and_cpu_half_request_run_in_float32(monkeypatch):
    observed = []

    def processor(images, **kwargs):
        observed.append(kwargs)
        return {"pixels": torch.arange(len(images) * 12).reshape(len(images), 3, 4).float()}

    def network(pixels):
        assert pixels.dtype == torch.float32
        return types.SimpleNamespace(predicted_depth=pixels)

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(
        AutoImageProcessor=None, AutoModelForDepthEstimation=None))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setitem(nodes._DEPTH_CACHE,
                        (nodes.DLSS5DepthAnythingV2.MODELS["Small (recommended)"], "cpu"),
                        (processor, network))
    images = torch.zeros(3, 8, 12, 3)
    depth, = nodes.DLSS5DepthAnythingV2().estimate(
        images, "Small (recommended)", True, 2, input_size=280, precision="FP16")
    assert len(observed) == 2
    assert all(call["size"] == {"height": 280, "width": 280} for call in observed)
    assert depth.shape == images.shape and depth.dtype == torch.float32
    assert torch.isfinite(depth).all() and depth.min() >= 0 and depth.max() <= 1


@pytest.fixture
def yolo(monkeypatch, tmp_path):
    backend = load("fast_depth_backend", "depth_backend.py")
    calls = []

    class Model:
        def __init__(self, path, **kwargs):
            calls.append(("load", str(path)))

        def predict(self, source, **kwargs):
            calls.append(("predict", kwargs))
            return [types.SimpleNamespace(depth=types.SimpleNamespace(
                data=torch.tensor([[1., 2., 4.], [1., 2., 4.]]))) for frame in source]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=Model))
    monkeypatch.setitem(sys.modules, "ultralytics.models.yolo.depth", types.SimpleNamespace(DepthPredictor=object))
    checks = types.SimpleNamespace(AUTOINSTALL=True)
    utils = types.SimpleNamespace(AUTOINSTALL=True, checks=checks)
    sys.modules["ultralytics"].utils = utils
    monkeypatch.setitem(sys.modules, "ultralytics.utils", utils)
    monkeypatch.setenv("YOLO_AUTOINSTALL", "true")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setitem(sys.modules, "folder_paths", types.SimpleNamespace(models_dir=str(tmp_path)))
    return backend, calls


def test_yolo_inverse_depth_shape_batching_cache_and_progress(yolo):
    backend, calls = yolo
    images = torch.zeros(5, 2, 3, 3)
    progress = []
    result = backend.infer_yolo_depth(images, "nano", 280, "FP16", 2, True,
                                      progress=progress.append)
    assert result.shape == images.shape and result.dtype == torch.float32
    assert result.device == images.device
    assert torch.all(result[..., 0, 0] > result[..., 2, 0])
    assert result.min() >= 0 and result.max() <= 1
    assert progress == [2, 4, 5]
    assert len([x for x in calls if x[0] == "load"]) == 1
    assert all(not x[1]["half"] and x[1]["imgsz"] == 288 for x in calls if x[0] == "predict")
    backend.infer_yolo_depth(images[:1], "nano", 280, "FP16", 2, True)
    assert len([x for x in calls if x[0] == "load"]) == 1


def test_yolo_old_dependency_fails_before_model_construction(monkeypatch):
    backend = load("fast_depth_backend", "depth_backend.py")
    calls = []
    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=lambda *a: calls.append(a)))
    monkeypatch.setitem(sys.modules, "ultralytics.models.yolo.depth", None)
    with pytest.raises(RuntimeError, match="Ultralytics.*depth"):
        backend.infer_yolo_depth(torch.zeros(1, 2, 3, 3), "nano", 280, "FP32", 1, True)
    assert calls == []


def test_yolo_cancellation_stops_before_next_batch(yolo):
    backend, calls = yolo
    completed = []

    def cancel():
        if completed:
            raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        backend.infer_yolo_depth(torch.zeros(5, 2, 3, 3), "nano", 280, "FP32", 2, True,
                                 check_cancel=cancel, progress=completed.append)
    assert len([x for x in calls if x[0] == "predict"]) == 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0., -1.])
def test_yolo_rejects_invalid_model_outputs(yolo, monkeypatch, bad):
    backend, _ = yolo
    monkeypatch.setattr(sys.modules["ultralytics"].YOLO, "predict", lambda *a, **kw: [
        types.SimpleNamespace(depth=types.SimpleNamespace(data=torch.full((2, 3), bad)))])
    with pytest.raises(RuntimeError, match="depth"):
        backend.infer_yolo_depth(torch.zeros(1, 2, 3, 3), "nano", 280, "FP32", 1, True)


def test_engine_requires_existing_file_and_cuda(yolo, tmp_path):
    backend, _ = yolo
    missing = tmp_path / "nano.engine"
    with pytest.raises(ValueError, match="engine"):
        backend.infer_yolo_depth(torch.zeros(1, 2, 3, 3), "nano", 280, "FP32", 1, True,
                                 engine_path=str(missing))
    missing.touch()
    with pytest.raises(ValueError, match="CUDA"):
        backend.infer_yolo_depth(torch.zeros(1, 2, 3, 3), "nano", 280, "FP32", 1, True,
                                 engine_path=str(missing))


def test_easy_override_routes_selected_guide_and_motion(monkeypatch):
    assert hasattr(nodes, "DLSS5DepthGuide")
    seen = []
    monkeypatch.setattr(nodes, "_bridge_diagnostics", lambda stages: (True, "ok"))
    monkeypatch.setattr(nodes.DLSS5DepthGuide, "estimate", lambda self, image, *a, **kw:
                        (seen.append((a, kw)) or torch.ones_like(image), "selected guide"))
    monkeypatch.setattr(nodes.DLSS5OpticalFlow, "estimate", lambda self, image, *a: (torch.full_like(image, 0.5),))
    monkeypatch.setattr(nodes.DLSS5RAFTFlow, "estimate", lambda *a: pytest.fail("override must avoid RAFT"))
    monkeypatch.setattr(nodes.DLSS5TemporalDepthStabilize, "stabilize", lambda self, image, *a: (image,))
    monkeypatch.setattr(nodes.DLSS5FullPipeline, "run", lambda self, image, *a: (image, "native"))
    image = torch.zeros(2, 8, 12, 3)
    result, report = nodes.DLSS5EasyPipeline().run(
        image, "Short video / best quality", "Upscale + neural rendering", "2x", "Quality",
        "Neutral / faithful", 0.85, depth_model="YOLO26 Nano (optional)", depth_input_size=280,
        depth_precision="FP16", motion_model="Optical Flow (fastest)")
    assert result is image
    assert seen[0][0][:4] == ("YOLO26 Nano (optional)", 280, "FP16", True)
    assert "selected guide" in report and "YOLO26 Nano" in report


def test_easy_low_resolution_motion_preserves_normalized_vector_units(monkeypatch):
    calls = []
    monkeypatch.setattr(nodes, "_bridge_diagnostics", lambda stages: (True, "ok"))
    monkeypatch.setattr(nodes.DLSS5DepthAnythingV2, "estimate", lambda self, image, *a: (image,))

    def flow(self, image, *args):
        calls.append(image.shape)
        result = torch.full_like(image, 0.5)
        result[1:, ..., 0] = 0.75
        return (result,)

    monkeypatch.setattr(nodes.DLSS5OpticalFlow, "estimate", flow)
    monkeypatch.setattr(nodes.DLSS5TemporalDepthStabilize, "stabilize", lambda self, depth, *a: (depth,))

    def native(self, image, depth, motion, *args):
        assert motion.shape == image.shape
        torch.testing.assert_close(motion[0], torch.full_like(motion[0], 0.5))
        torch.testing.assert_close(motion[1, ..., 0], torch.full_like(motion[1, ..., 0], 0.75))
        return image, "native"

    monkeypatch.setattr(nodes.DLSS5FullPipeline, "run", native)
    image = torch.zeros(2, 8, 12, 3)
    nodes.DLSS5EasyPipeline().run(image, "Still image", "Upscale + neural rendering", "2x",
        "Quality", "Neutral / faithful", 0.85, motion_input_size=6)
    assert calls == [(2, 4, 6, 3)]


def test_benchmark_timing_and_strict_throughput_gate():
    assert (ROOT / "tools/benchmark_fast_depth.py").is_file()
    benchmark = load("fast_depth_benchmark", "tools/benchmark_fast_depth.py")
    ticks = iter([0., 0.1, 1., 1.2, 2., 2.3])
    samples, result = benchmark.measure(lambda: "result", 0, 3, sync=lambda: None,
                                        clock=lambda: next(ticks))
    assert result == "result"
    assert samples == pytest.approx([0.1, 0.2, 0.3])
    assert benchmark.gate_passes([0.1, 0.2, 0.3], frames=8, minimum_fps=30)
    assert not benchmark.gate_passes([0.3, 0.4, 0.5], frames=8, minimum_fps=30)
    assert not benchmark.gate_passes([1.0], frames=30, minimum_fps=30)
    assert not benchmark.gate_passes([0.1], frames=8, minimum_fps=30, output_size=(1920, 1080))


def test_engine_report_does_not_claim_requested_shape_as_effective(monkeypatch):
    monkeypatch.setattr(nodes, "infer_yolo_depth", lambda images, *a, **kw: images)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    _, report = nodes.DLSS5DepthGuide().estimate(torch.zeros(1, 2, 3, 3),
        "YOLO26 Nano (optional)", 392, "FP16", True, 4, engine_path="fixed768.engine")
    assert "requested_input_size=416" in report
    assert "effective_input_size=engine-defined" in report
    assert "fixed768.engine" in report


def test_benchmark_loads_nodes_in_a_package_for_vda(monkeypatch):
    benchmark = load("fast_depth_benchmark", "tools/benchmark_fast_depth.py")
    assert hasattr(benchmark, "load_nodes")
    loaded = benchmark.load_nodes()
    image = torch.zeros(2, 2, 3, 3)
    monkeypatch.setitem(sys.modules, loaded.__package__ + ".video_depth_backend",
                        types.SimpleNamespace(infer_vda_small=lambda *a, **kw: image))
    depth, report = loaded.DLSS5DepthGuide().estimate(image,
        "Video Depth Anything Small", 280, "FP32", True, 4)
    assert depth is image
    assert "Video Depth Anything Small" in report


def test_yolo_resizes_before_host_preprocessing_and_restores_frame_order(yolo, monkeypatch):
    backend, _ = yolo
    seen = []

    def predict(self, source, **kwargs):
        seen.extend(frame.shape for frame in source)
        assert max(source[0].shape[:2]) <= 32
        # Inspect BGR red channel, proving frame chronology and RGB conversion.
        return [types.SimpleNamespace(depth=types.SimpleNamespace(
            data=torch.full(frame.shape[:2], 1. + float(frame[0, 0, 2]) / 255)))
                for frame in source]

    monkeypatch.setattr(sys.modules["ultralytics"].YOLO, "predict", predict)
    images = torch.zeros(2, 64, 96, 3)
    images[1, ..., 0] = 1.
    result = backend.infer_yolo_depth(images, "nano", 32, "FP32", 2, True)
    assert seen == [(21, 32, 3), (21, 32, 3)]
    assert result.shape == images.shape
    assert result[0].mean() > result[1].mean()


def test_yolo_disables_installation_even_when_ultralytics_was_preimported(yolo, monkeypatch):
    import os
    backend, _ = yolo
    model_cls = sys.modules["ultralytics"].YOLO
    original = model_cls.__init__
    installs = []

    def constructor(self, *args, **kwargs):
        utils = sys.modules["ultralytics.utils"]
        if utils.AUTOINSTALL or utils.checks.AUTOINSTALL or os.environ.get("YOLO_AUTOINSTALL") != "false":
            installs.append("dependency install")
        original(self, *args, **kwargs)

    monkeypatch.setattr(model_cls, "__init__", constructor)
    backend.infer_yolo_depth(torch.zeros(1, 2, 3, 3), "nano", 280, "FP32", 1, True)
    assert installs == []


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA memory regression requires a GPU")
def test_yolo_long_clip_keeps_intermediate_gpu_storage_bounded(yolo, monkeypatch):
    backend, _ = yolo
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    def predict(self, source, **kwargs):
        return [types.SimpleNamespace(depth=types.SimpleNamespace(
            data=torch.ones(frame.shape[:2], device="cuda"))) for frame in source]

    monkeypatch.setattr(sys.modules["ultralytics"].YOLO, "predict", predict)
    images = torch.zeros(64, 512, 768, 3)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    before = torch.cuda.memory_allocated()
    result = backend.infer_yolo_depth(images, "nano", 280, "FP16", 4, True)
    torch.cuda.synchronize()
    assert result.shape == images.shape and result.device.type == "cpu"
    assert torch.cuda.max_memory_allocated() - before < 128 * 1024**2
