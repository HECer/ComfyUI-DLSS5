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

