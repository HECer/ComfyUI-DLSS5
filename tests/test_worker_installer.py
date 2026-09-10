from pathlib import Path
import importlib.util

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_install_runtime", ROOT / "install_runtime.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_current_worker_is_not_downloaded(tmp_path, monkeypatch):
    worker = tmp_path / "dlssg-worker.exe"
    worker.write_bytes(b"current")
    digest = installer.sha256(worker)
    monkeypatch.setattr(installer, "DLSSG_WORKER_SHA256", digest)
    monkeypatch.setattr(
        installer,
        "download",
        lambda *_args, **_kwargs: pytest.fail("download should not run"),
    )

    assert installer.install_dlssg_worker(worker) == digest


def test_current_sr_runtime_is_not_downloaded(tmp_path, monkeypatch):
    runtime = tmp_path / "nvngx_dlss.dll"
    runtime.write_bytes(b"current sr runtime")
    digest = installer.sha256(runtime)
    monkeypatch.setattr(installer, "NVIDIA_DLSS_SHA256", digest)
    monkeypatch.setattr(
        installer,
        "download",
        lambda *_args, **_kwargs: pytest.fail("download should not run"),
    )

    assert installer.install_sr_runtime(runtime) == digest


def test_missing_sr_runtime_is_downloaded_and_verified(tmp_path, monkeypatch):
    runtime = tmp_path / "nvngx_dlss.dll"
    payload = b"pinned sr runtime"
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(payload)
    digest = installer.sha256(payload_path)
    payload_path.unlink()
    monkeypatch.setattr(installer, "NVIDIA_DLSS_SHA256", digest)
    monkeypatch.setattr(
        installer,
        "download",
        lambda _url, destination, _label: destination.write_bytes(payload),
    )

    assert installer.install_sr_runtime(runtime) == digest
    assert runtime.read_bytes() == payload


def test_known_legacy_worker_is_preserved(tmp_path, monkeypatch):
    worker = tmp_path / "dlssg-worker.exe"
    worker.write_bytes(b"legacy")
    legacy_digest = installer.sha256(worker)
    replacement = b"open source replacement"
    replacement_path = tmp_path / "replacement.exe"
    replacement_path.write_bytes(replacement)
    replacement_digest = installer.sha256(replacement_path)
    replacement_path.unlink()
    monkeypatch.setattr(installer, "DLSSG_LEGACY_WORKER_SHA256", {legacy_digest})
    monkeypatch.setattr(installer, "DLSSG_WORKER_SHA256", replacement_digest)
    monkeypatch.setattr(
        installer,
        "download",
        lambda _url, destination, _label: destination.write_bytes(replacement),
    )

    assert installer.install_dlssg_worker(worker) == replacement_digest
    assert worker.read_bytes() == replacement
    assert (tmp_path / f"dlssg-worker.legacy-{legacy_digest[:8]}.exe").read_bytes() == b"legacy"


def test_unknown_existing_worker_is_left_untouched(tmp_path, monkeypatch):
    worker = tmp_path / "dlssg-worker.exe"
    worker.write_bytes(b"unknown")
    monkeypatch.setattr(installer, "DLSSG_LEGACY_WORKER_SHA256", set())

    with pytest.raises(RuntimeError, match="unknown SHA-256"):
        installer.install_dlssg_worker(worker)

    assert worker.read_bytes() == b"unknown"


def test_bundled_vapoursynth_wrappers_are_in_the_package():
    for name in ("vsdlssnr.dll", "vsdlsssr.dll"):
        path = ROOT / "runtime" / name
        assert path.is_file(), f"missing bundled wrapper: {path}"
        assert path.stat().st_size > 16 * 1024


def test_bundled_nvidia_runtimes_are_in_the_package():
    expected = {
        "nvngx_dlss.dll": "be6e434a94ca32499515eb62ca0e6c274526055d568d0426e4c652dcdfb6ee6e",
        "nvngx_dlssnr.dll": "8270b350cd82de5ce89806872cdd6b6a9249b80836b91bbeb3573470744cc206",
        "dlssg/nvngx_dlssg.dll": "c64928fdb7c48a57722ea8eef2662171edc323473adea66c29a206a23f1a2bed",
    }
    for relative, digest in expected.items():
        path = ROOT / "runtime" / relative
        assert path.is_file(), f"missing bundled NVIDIA runtime: {path}"
        assert installer.sha256(path) == digest


def test_bundled_wrappers_are_staged_next_to_sr_runtime(tmp_path, monkeypatch):
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "vsdlssnr.dll").write_bytes(b"nr-wrapper")
    (source / "vsdlsssr.dll").write_bytes(b"sr-wrapper")
    monkeypatch.setattr(installer, "RUNTIME", source)

    destination = tmp_path / "vapourkit" / "plugins"
    nr_plugin, sr_plugin = installer.stage_bundled_plugins(destination)

    assert nr_plugin == destination / "vsdlssnr.dll"
    assert sr_plugin == destination / "vsdlsssr.dll"
    assert nr_plugin.read_bytes() == b"nr-wrapper"
    assert sr_plugin.read_bytes() == b"sr-wrapper"
