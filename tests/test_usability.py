from __future__ import annotations

import importlib.util
import hashlib
import json
import os
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
        runtime / "nvngx_dlss.dll",
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
    monkeypatch.setattr(install_runtime, "ensure_bridge_numpy", lambda _path: "2.5.2")

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


def _base_install_fixture(monkeypatch, tmp_path, config=None):
    runtime = tmp_path / "runtime"
    extracted = runtime / install_runtime.RELEASE
    extracted.mkdir(parents=True)
    (extracted / ".extracted-ok").write_text(install_runtime.SHA256, encoding="utf-8")
    (runtime / install_runtime.ARCHIVE).write_bytes(b"archive")
    for name in ("nvngx_dlss.dll", "nvngx_dlssnr.dll", "vsdlssnr.dll", "vsdlsssr.dll"):
        (runtime / name).write_bytes(name.encode())
    if config is not None:
        (runtime / "config.json").write_text(json.dumps(config), encoding="utf-8")
    python = extracted / "python.exe"
    python.touch()
    monkeypatch.setattr(install_runtime, "RUNTIME", runtime)
    monkeypatch.setitem(sys.modules, "py7zr", types.SimpleNamespace())
    monkeypatch.setattr(install_runtime, "sha256", lambda path: install_runtime.SHA256)
    monkeypatch.setattr(
        install_runtime,
        "verify_runtime_hash",
        lambda _path, expected, _label: expected,
    )
    monkeypatch.setattr(
        install_runtime,
        "stage_bundled_plugins",
        lambda _path: (runtime / "vsdlssnr.dll", runtime / "vsdlsssr.dll"),
    )
    monkeypatch.setattr(install_runtime, "find_vapour_python", lambda _path: python)
    monkeypatch.setattr(install_runtime, "ensure_bridge_numpy", lambda _path: "2.5.2")
    return runtime


def test_base_install_succeeds_without_fg_and_preserves_optional_state(monkeypatch, tmp_path):
    original_config = {
        "custom": "kept",
        "dlssg_runtime": "D:/existing/nvngx_dlssg.dll",
        "dlssg_worker": "D:/existing/dlssg-worker.exe",
        "dlssg_worker_sha256": "existing-worker-hash",
    }
    runtime = _base_install_fixture(monkeypatch, tmp_path, original_config)
    worker = runtime / "dlssg" / "dlssg-worker.exe"
    worker.parent.mkdir()
    worker.write_bytes(b"existing worker")
    monkeypatch.setattr(
        install_runtime,
        "install_dlssg_worker",
        lambda _path: pytest.fail("base install must not install Frame Generation"),
    )
    monkeypatch.setattr(
        install_runtime,
        "download",
        lambda *_args: pytest.fail("fixture is complete; no download should run"),
    )

    report = install_runtime.install()

    written = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    assert worker.read_bytes() == b"existing worker"
    assert written["custom"] == "kept"
    assert written["dlssg_runtime"] == original_config["dlssg_runtime"]
    assert written["dlssg_worker"] == original_config["dlssg_worker"]
    assert written["dlssg_worker_sha256"] == "existing-worker-hash"
    assert "Frame Generation" not in report


@pytest.mark.parametrize("missing", ["nvngx_dlss.dll", "nvngx_dlssnr.dll"])
def test_base_install_rejects_missing_required_asset_before_downloads(
    monkeypatch, tmp_path, missing
):
    runtime = _base_install_fixture(monkeypatch, tmp_path)
    (runtime / missing).unlink()
    downloads = []
    monkeypatch.setattr(
        install_runtime,
        "download",
        lambda url, _destination, label: downloads.append((url, label)),
    )

    with pytest.raises(RuntimeError, match=missing):
        install_runtime.install()

    assert downloads == []


def test_fg_install_validates_runtime_then_worker_and_updates_config(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    dlssg = runtime / "dlssg"
    dlssg.mkdir(parents=True)
    fg_runtime = dlssg / "nvngx_dlssg.dll"
    fg_runtime.write_bytes(b"runtime")
    (runtime / "config.json").write_text(json.dumps({"custom": "kept"}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(install_runtime, "RUNTIME", runtime)
    monkeypatch.setattr(
        install_runtime,
        "verify_runtime_hash",
        lambda path, expected, label: calls.append((path, expected, label)) or "runtime-hash",
    )
    monkeypatch.setattr(
        install_runtime,
        "install_dlssg_worker",
        lambda path: calls.append((path,)) or "worker-hash",
    )

    report = install_runtime.install_frame_generation()

    worker = dlssg / "dlssg-worker.exe"
    assert calls == [
        (fg_runtime, install_runtime.NVIDIA_DLSSG_SHA256, "NVIDIA DLSS-G runtime"),
        (worker,),
    ]
    written = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    assert written["custom"] == "kept"
    assert written["dlssg_runtime"] == str(fg_runtime.resolve())
    assert written["dlssg_runtime_sha256"] == "runtime-hash"
    assert written["dlssg_worker"] == str(worker.resolve())
    assert written["dlssg_worker_sha256"] == "worker-hash"
    assert "Frame Generation setup complete" in report


def test_fg_install_rejects_runtime_mismatch_before_worker_download(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "dlssg").mkdir(parents=True)
    monkeypatch.setattr(install_runtime, "RUNTIME", runtime)
    monkeypatch.setattr(
        install_runtime,
        "verify_runtime_hash",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("SHA-256 mismatch")),
    )
    monkeypatch.setattr(
        install_runtime,
        "install_dlssg_worker",
        lambda _path: pytest.fail("worker download must follow runtime validation"),
    )

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        install_runtime.install_frame_generation()


def test_fg_install_is_appended_to_setup_actions_and_cli_routes(monkeypatch):
    actions = nodes.DLSS5RuntimeSetup.INPUT_TYPES()["required"]["action"][0]
    assert actions[:2] == ["Check location", "Install verified VapourKit"]
    assert actions[2] == "Install verified Frame Generation"

    calls = []
    monkeypatch.setattr(install_runtime, "install", lambda: calls.append("base") or "base")
    monkeypatch.setattr(
        install_runtime,
        "install_frame_generation",
        lambda: calls.append("fg") or "fg",
    )
    assert install_runtime.main([]) == 0
    assert install_runtime.main(["--install-frame-generation"]) == 0
    assert calls == ["base", "fg"]

    script = (ROOT / "install_runtime.ps1").read_text(encoding="utf-8-sig")
    assert "[switch] $InstallFrameGeneration" in script
    assert "--install-frame-generation" in script
    manual_script = (ROOT / "setup.ps1").read_text(encoding="utf-8-sig")
    assert "import vapoursynth, numpy" in manual_script
    assert "pinned NumPy bridge dependency" in manual_script


def _fg_hash_fixture(monkeypatch, tmp_path, downloaded=b"verified worker fixture"):
    runtime = tmp_path / "runtime"
    fg = runtime / "dlssg"
    fg.mkdir(parents=True)
    runtime_bytes = b"verified runtime fixture"
    (fg / "nvngx_dlssg.dll").write_bytes(runtime_bytes)
    config = runtime / "config.json"
    config.write_bytes(b'{"custom":"kept","timeout_seconds":71}\n')
    monkeypatch.setattr(install_runtime, "RUNTIME", runtime)
    monkeypatch.setattr(install_runtime, "NVIDIA_DLSSG_SHA256", hashlib.sha256(runtime_bytes).hexdigest())
    monkeypatch.setattr(install_runtime, "DLSSG_WORKER_SHA256", hashlib.sha256(b"verified worker fixture").hexdigest())
    downloads = []

    def download(url, destination, label):
        assert url == install_runtime.DLSSG_WORKER_URL
        assert destination == fg / "dlssg-worker.exe"
        downloads.append(url)
        destination.write_bytes(downloaded)

    monkeypatch.setattr(install_runtime, "download", download)
    return runtime, config, downloads


def test_fg_install_checks_actual_runtime_and_downloaded_worker_hashes(monkeypatch, tmp_path):
    runtime, config, downloads = _fg_hash_fixture(monkeypatch, tmp_path)
    report = install_runtime.install_frame_generation()
    written = json.loads(config.read_text(encoding="utf-8"))
    assert (runtime / "dlssg" / "dlssg-worker.exe").read_bytes() == b"verified worker fixture"
    assert written["dlssg_runtime_sha256"] == hashlib.sha256(b"verified runtime fixture").hexdigest()
    assert written["dlssg_worker_sha256"] == hashlib.sha256(b"verified worker fixture").hexdigest()
    assert written["custom"] == "kept" and written["timeout_seconds"] == 71
    assert downloads == [install_runtime.DLSSG_WORKER_URL]
    assert "Frame Generation setup complete" in report


@pytest.mark.parametrize("corrupt", ["runtime", "downloaded_worker"])
def test_fg_install_real_hash_mismatch_preserves_config(monkeypatch, tmp_path, corrupt):
    downloaded = b"corrupt worker" if corrupt == "downloaded_worker" else b"verified worker fixture"
    runtime, config, downloads = _fg_hash_fixture(monkeypatch, tmp_path, downloaded)
    original = config.read_bytes()
    fg = runtime / "dlssg"
    if corrupt == "runtime":
        (fg / "nvngx_dlssg.dll").write_bytes(b"corrupt runtime")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        install_runtime.install_frame_generation()
    assert config.read_bytes() == original
    assert not (fg / "dlssg-worker.exe").exists()
    if corrupt == "runtime":
        assert downloads == []
    else:
        assert downloads == [install_runtime.DLSSG_WORKER_URL]
        assert (fg / "dlssg-worker.exe.unverified").read_bytes() == b"corrupt worker"


@pytest.mark.parametrize("confirmed", [False, True])
def test_fg_install_setup_action_executes_only_after_confirmation(monkeypatch, tmp_path, confirmed):
    runtime, config, downloads = _fg_hash_fixture(monkeypatch, tmp_path)
    original = config.read_bytes()
    package = types.ModuleType("usability_fg_action")
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(sys.modules, package.__name__ + ".install_runtime", install_runtime)
    action_nodes = _load_module(package.__name__ + ".nodes", ROOT / "nodes.py")
    monkeypatch.setattr(action_nodes, "PACKAGE", tmp_path)
    result = action_nodes.DLSS5RuntimeSetup().run("Install verified Frame Generation", confirmed)
    if confirmed:
        assert "Frame Generation setup complete" in result[0]
        assert downloads == [install_runtime.DLSSG_WORKER_URL]
        assert (runtime / "dlssg" / "dlssg-worker.exe").read_bytes() == b"verified worker fixture"
        assert json.loads(config.read_text(encoding="utf-8"))["custom"] == "kept"
    else:
        assert "Download not started" in result[0]
        assert downloads == []
        assert config.read_bytes() == original
        assert not (runtime / "dlssg" / "dlssg-worker.exe").exists()


@pytest.mark.parametrize("fallback", [False, True])
def test_bridge_numpy_manual_probe_handles_native_stderr_and_tries_next(tmp_path, fallback):
    repo, comfy, vapourkit, nr, sr = _manual_setup_fixture(tmp_path)
    # A real native executable emitting stderr/nonzero models a failed import.
    bad = vapourkit / "python.exe"
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        pytest.skip("Windows .NET Framework compiler required for native stderr fixture")
    source = tmp_path / "failed_probe.cs"
    source.write_text('class Probe { static int Main() { System.Console.Error.WriteLine("ModuleNotFoundError: No module named numpy"); return 1; } }', encoding="utf-8")
    subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(bad), str(source)], check=True, capture_output=True, timeout=30)
    failed_probe = subprocess.run([str(bad), "-c", "import vapoursynth, numpy"], capture_output=True)
    assert failed_probe.returncode != 0 and failed_probe.stderr
    good = vapourkit / "next" / "python.exe"
    if fallback:
        good.parent.mkdir()
        shutil.copy2(shutil.which("cmd.exe"), good)
    config = repo / "runtime" / "config.json"
    prior = b'{"custom":"preserve","timeout_seconds":71}\n'
    config.write_bytes(prior)
    result = _run_setup(repo, comfy, vapourkit, nr, sr)
    if fallback:
        assert result.returncode == 0, result.stderr
        written = json.loads(config.read_text(encoding="utf-8-sig"))
        assert Path(written["python"]).resolve() == good.resolve()
        assert written["custom"] == "preserve"
    else:
        assert result.returncode != 0
        assert "pinned NumPy bridge dependency" in result.stderr
        assert config.read_bytes() == prior
        assert not (comfy / "custom_nodes" / "ComfyUI-DLSS5").exists()


@pytest.mark.parametrize(("fg", "exit_code"), [(False, 0), (True, 0), (True, 7)])
def test_fg_install_powershell_forwards_arguments_and_exit_code(tmp_path, fg, exit_code):
    powershell = shutil.which("powershell")
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if powershell is None or not compiler.is_file():
        pytest.skip("Windows PowerShell and .NET compiler required for headless routing test")
    repo = tmp_path / "ComfyUI" / "custom_nodes" / "Extension With Spaces"
    repo.mkdir(parents=True)
    shutil.copy2(ROOT / "install_runtime.ps1", repo / "install_runtime.ps1")
    (repo / "install_runtime.py").touch()
    python = tmp_path / "python_embeded" / "python.exe"
    python.parent.mkdir()
    source = tmp_path / "record_args.cs"
    source.write_text(
        'class Probe { static int Main(string[] args) { '
        'string dir = System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location); '
        'System.IO.File.WriteAllLines(System.IO.Path.Combine(dir, "args.txt"), args); '
        f'return {exit_code}; }} }}', encoding="utf-8"
    )
    subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(python), str(source)], check=True, capture_output=True, timeout=30)
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(repo / "install_runtime.ps1")]
    if fg:
        command.append("-InstallFrameGeneration")
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, cwd=repo)
    assert result.returncode == exit_code, result.stderr
    actual = (python.parent / "args.txt").read_text(encoding="utf-8-sig").splitlines()
    expected = [str(repo / "install_runtime.py")]
    if fg:
        expected.append("--install-frame-generation")
    assert actual == expected


def test_bridge_numpy_preserves_an_existing_working_version(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    commands = []

    def run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="2.1.0\n", stderr="")

    monkeypatch.setattr(install_runtime.subprocess, "run", run)

    assert install_runtime.ensure_bridge_numpy(python) == "2.1.0"
    assert len(commands) == 1
    assert commands[0][0][0] == str(python)
    assert "numpy" in commands[0][0][2]
    assert commands[0][1]["timeout"] == install_runtime.BRIDGE_PROBE_TIMEOUT_SECONDS


def test_bridge_numpy_installs_pinned_version_only_in_bridge_python(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    results = iter(
        [
            subprocess.CompletedProcess([], 1, stdout="", stderr="No module named numpy"),
            subprocess.CompletedProcess([], 0, stdout="installed", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="2.5.2\n", stderr=""),
        ]
    )
    commands = []

    def run(command, **kwargs):
        commands.append((command, kwargs))
        return next(results)

    monkeypatch.setattr(install_runtime.subprocess, "run", run)

    assert install_runtime.ensure_bridge_numpy(python) == "2.5.2"
    assert commands[1][0] == [
        str(python),
        "-m",
        "pip",
        "install",
        f"numpy=={install_runtime.NUMPY_VERSION}",
    ]
    assert commands[1][1]["timeout"] == install_runtime.BRIDGE_INSTALL_TIMEOUT_SECONDS
    assert all(command[0] == str(python) for command, _kwargs in commands)
    assert all("torch" not in " ".join(command).lower() for command, _kwargs in commands)


@pytest.mark.parametrize(
    ("results", "message"),
    [
        (
            [
                subprocess.CompletedProcess([], 1, stdout="", stderr="missing"),
                subprocess.CompletedProcess([], 1, stdout="", stderr="pip failed"),
            ],
            "NumPy installation failed",
        ),
        (
            [
                subprocess.CompletedProcess([], 1, stdout="", stderr="missing"),
                subprocess.TimeoutExpired([], 300),
            ],
            "Timed out installing NumPy",
        ),
        (
            [
                subprocess.CompletedProcess([], 1, stdout="", stderr="missing"),
                subprocess.CompletedProcess([], 0, stdout="installed", stderr=""),
                subprocess.CompletedProcess([], 1, stdout="", stderr="still missing"),
            ],
            "NumPy remains unavailable",
        ),
        (
            [subprocess.TimeoutExpired([], 30)],
            "Timed out while checking NumPy",
        ),
    ],
)
def test_bridge_numpy_failures_are_actionable_and_preserve_config(
    monkeypatch, tmp_path, results, message
):
    ensure_bridge_numpy = install_runtime.ensure_bridge_numpy
    runtime = _base_install_fixture(monkeypatch, tmp_path, {"custom": "unchanged"})
    original = (runtime / "config.json").read_bytes()
    outcomes = iter(results)

    def run(_command, **_kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(install_runtime, "ensure_bridge_numpy", ensure_bridge_numpy)
    monkeypatch.setattr(install_runtime.subprocess, "run", run)

    with pytest.raises(RuntimeError, match=message):
        install_runtime.install()

    assert (runtime / "config.json").read_bytes() == original
