from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nodes = _load_module("usability_nodes", ROOT / "nodes.py")
install_runtime = _load_module("usability_install_runtime", ROOT / "install_runtime.py")


def test_config_roundtrip_reads_utf8_with_or_without_bom(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(nodes, "PACKAGE", tmp_path)
    expected = {"temp_dir": "custom", "timeout_seconds": 17, "extra": True}

    for encoding in ("utf-8", "utf-8-sig"):
        (runtime / "config.json").write_text(json.dumps(expected), encoding=encoding)
        assert nodes._runtime_config() == expected


@pytest.mark.parametrize("content", ["{broken", "[]"])
def test_config_roundtrip_reports_invalid_configuration(monkeypatch, tmp_path, content):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "config.json").write_text(content, encoding="utf-8")
    monkeypatch.setattr(nodes, "PACKAGE", tmp_path)

    with pytest.raises(RuntimeError, match="runtime configuration"):
        nodes._runtime_config()


def test_config_roundtrip_installer_preserves_custom_settings(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    extracted = runtime / install_runtime.RELEASE
    dlssg = runtime / "dlssg"
    extracted.mkdir(parents=True)
    dlssg.mkdir()
    (extracted / ".extracted-ok").write_text("ok", encoding="utf-8")
    for path in (
        runtime / "nvngx_dlssnr.dll",
        dlssg / "nvngx_dlssg.dll",
        runtime / install_runtime.ARCHIVE,
    ):
        path.touch()

    custom_temp = tmp_path / "custom-temp"
    existing = {
        "temp_dir": str(custom_temp),
        "timeout_seconds": 29,
        "custom_setting": {"kept": True},
    }
    (runtime / "config.json").write_text(
        json.dumps(existing), encoding="utf-8-sig"
    )

    nr_plugin = runtime / "vsdlssnr.dll"
    sr_plugin = runtime / "vsdlsssr.dll"
    python = extracted / "python.exe"
    monkeypatch.setattr(install_runtime, "RUNTIME", runtime)
    monkeypatch.setitem(sys.modules, "py7zr", types.SimpleNamespace())
    monkeypatch.setattr(install_runtime, "install_dlssg_worker", lambda _path: "worker")
    monkeypatch.setattr(install_runtime, "install_sr_runtime", lambda _path: "sr")
    monkeypatch.setattr(install_runtime, "verify_runtime_hash", lambda *_args: "runtime")
    monkeypatch.setattr(install_runtime, "sha256", lambda _path: install_runtime.SHA256)
    monkeypatch.setattr(
        install_runtime, "stage_bundled_plugins", lambda _path: (nr_plugin, sr_plugin)
    )
    monkeypatch.setattr(install_runtime, "find_vapour_python", lambda _path: python)

    install_runtime.install()

    written = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    assert written["temp_dir"] == str(custom_temp)
    assert written["timeout_seconds"] == 29
    assert written["custom_setting"] == {"kept": True}
    assert custom_temp.is_dir()
    assert not (runtime / "config.json").read_bytes().startswith(b"\xef\xbb\xbf")


def _manual_setup_fixture(root: Path):
    repo = root / "repo"
    comfy = root / "comfy"
    sources = root / "sources"
    vapourkit = root / "vapourkit"
    runtime = repo / "runtime"
    runtime.mkdir(parents=True)
    comfy.mkdir()
    sources.mkdir()
    vapourkit.mkdir()
    shutil.copy2(ROOT / "setup.ps1", repo / "setup.ps1")
    shutil.copy2(shutil.which("cmd.exe"), vapourkit / "python.exe")
    for name in ("vsdlssnr.dll", "vsdlsssr.dll"):
        (runtime / name).touch()
    nr = sources / "nvngx_dlssnr.dll"
    sr = sources / "nvngx_dlss.dll"
    nr.touch()
    sr.touch()
    return repo, comfy, vapourkit, nr, sr


def _run_setup(repo: Path, comfy: Path, vapourkit: Path, nr: Path, sr: Path):
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is required for the manual setup regression")
    return subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo / "setup.ps1"),
            "-ComfyUIPath",
            str(comfy),
            "-VapourKitPath",
            str(vapourkit),
            "-NeuralRuntimeDll",
            str(nr),
            "-SRRuntimeDll",
            str(sr),
        ],
        capture_output=True,
        text=True,
        cwd=repo,
    )


def test_setup_repeatable_accepts_existing_junction_and_preserves_config(tmp_path):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    first = _run_setup(repo, comfy, vapourkit, nr, sr)
    assert first.returncode == 0, first.stderr

    config_path = repo / "runtime" / "config.json"
    custom_temp = tmp_path / "kept-temp"
    custom_temp.mkdir()
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    config.update(
        temp_dir=str(custom_temp),
        timeout_seconds=41,
        custom_setting="Gr\u00fc\u00dfe",
        nested_setting={"level1": {"level2": {"kept": True}}},
    )
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    second = _run_setup(repo, comfy, vapourkit, nr, sr)

    assert second.returncode == 0, second.stderr
    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["temp_dir"] == str(custom_temp)
    assert written["timeout_seconds"] == 41
    assert written["custom_setting"] == "Gr\u00fc\u00dfe"
    assert written["nested_setting"] == {"level1": {"level2": {"kept": True}}}
    assert not config_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not list(config_path.parent.glob("config.json.*.tmp"))


def test_setup_repeatable_rejects_conflict_before_writes_and_keeps_config(tmp_path):
    first_repo, comfy, first_vapourkit, first_nr, first_sr = _manual_setup_fixture(
        tmp_path / "first"
    )
    first = _run_setup(first_repo, comfy, first_vapourkit, first_nr, first_sr)
    assert first.returncode == 0, first.stderr

    second_repo, _unused_comfy, second_vapourkit, second_nr, second_sr = (
        _manual_setup_fixture(tmp_path / "second")
    )
    config_path = second_repo / "runtime" / "config.json"
    prior = b'{"temp_dir":"still-usable","timeout_seconds":7}\n'
    config_path.write_bytes(prior)

    conflict = _run_setup(
        second_repo, comfy, second_vapourkit, second_nr, second_sr
    )

    assert conflict.returncode != 0
    assert "already exists" in conflict.stderr
    assert config_path.read_bytes() == prior
    assert not (second_repo / "runtime" / "nvngx_dlssnr.dll").exists()
    assert not (second_repo / "runtime" / "nvngx_dlss.dll").exists()


def test_setup_repeatable_keeps_config_when_junction_creation_fails(tmp_path):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    config_path = repo / "runtime" / "config.json"
    prior = b'{"temp_dir":"still-usable","timeout_seconds":7}\n'
    config_path.write_bytes(prior)
    (comfy / "custom_nodes").write_text("not a directory", encoding="utf-8")

    failed = _run_setup(repo, comfy, vapourkit, nr, sr)

    assert failed.returncode != 0
    assert config_path.read_bytes() == prior


@pytest.mark.parametrize("content", ["123", '"text"', "true", "null", "[]", "[1]", '[{"x":1}]'])
def test_config_roundtrip_manual_setup_rejects_non_object_before_writes(tmp_path, content):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    config_path = repo / "runtime" / "config.json"
    prior = content.encode("utf-8")
    config_path.write_bytes(prior)
    failed = _run_setup(repo, comfy, vapourkit, nr, sr)
    assert failed.returncode != 0
    assert "expected a JSON object" in failed.stderr
    assert config_path.read_bytes() == prior
    assert not (comfy / "custom_nodes" / "ComfyUI-DLSS5").exists()
    assert not (repo / "runtime" / "nvngx_dlssnr.dll").exists()
    assert not (repo / "runtime" / "nvngx_dlss.dll").exists()


def test_setup_repeatable_does_not_leave_junction_after_validation_failure(tmp_path):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    nr.unlink()

    failed = _run_setup(repo, comfy, vapourkit, nr, sr)

    assert failed.returncode != 0
    assert not (comfy / "custom_nodes" / "ComfyUI-DLSS5").exists()


def test_setup_repeatable_does_not_create_junction_when_config_preparation_fails(tmp_path):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    temp_path = tmp_path / "not-a-directory"
    temp_path.touch()
    config_path = repo / "runtime" / "config.json"
    prior = json.dumps({"temp_dir": str(temp_path / "child"), "timeout_seconds": 7}).encode()
    config_path.write_bytes(prior)

    failed = _run_setup(repo, comfy, vapourkit, nr, sr)

    assert failed.returncode != 0
    assert config_path.read_bytes() == prior
    assert not (comfy / "custom_nodes" / "ComfyUI-DLSS5").exists()
    assert not list(config_path.parent.glob("config.json.*.tmp"))


@pytest.mark.parametrize("existing_junction", [False, True])
def test_setup_repeatable_rolls_back_only_new_junction_when_config_replace_fails(
    tmp_path, existing_junction
):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    if existing_junction:
        first = _run_setup(repo, comfy, vapourkit, nr, sr)
        assert first.returncode == 0, first.stderr
    config_path = repo / "runtime" / "config.json"
    prior = json.dumps({"temp_dir": str(tmp_path / "temp"), "timeout_seconds": 7}).encode()
    config_path.write_bytes(prior)
    config_path.chmod(stat.S_IREAD)
    try:
        failed = _run_setup(repo, comfy, vapourkit, nr, sr)
    finally:
        config_path.chmod(stat.S_IWRITE)

    assert failed.returncode != 0
    assert "Replace" in failed.stderr
    assert config_path.read_bytes() == prior
    junction = comfy / "custom_nodes" / "ComfyUI-DLSS5"
    assert junction.exists() == existing_junction
    if existing_junction:
        assert junction.resolve() == repo.resolve()
    assert (repo / "setup.ps1").is_file()
    assert (repo / "runtime" / "vsdlssnr.dll").is_file()
    assert not list(config_path.parent.glob("config.json.*.tmp"))
    assert not list(config_path.parent.glob("config.json.*.bak"))
