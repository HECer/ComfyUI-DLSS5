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
    assert "Repair the selected interpreter" in manual_script
    assert "does not repair the external environment selected by -VapourKitPath" in manual_script


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
        assert "Frame Generation setup complete" in result["result"][0]
        assert downloads == [install_runtime.DLSSG_WORKER_URL]
        assert (runtime / "dlssg" / "dlssg-worker.exe").read_bytes() == b"verified worker fixture"
        assert json.loads(config.read_text(encoding="utf-8"))["custom"] == "kept"
    else:
        assert "Download not started" in result["result"][0]
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
        assert "selected interpreter" in result.stderr
        assert "does not repair" in result.stderr
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


def _schema_contract(node_class):
    schema = node_class.INPUT_TYPES()
    return {
        group: {
            name: (
                value[0],
                {key: setting for key, setting in value[1].items() if key != "tooltip"}
                if len(value) > 1
                else {},
            )
            for name, value in fields.items()
        }
        for group, fields in schema.items()
    }


def _baseline_nodes():
    source = subprocess.run(
        ["git", "show", "9d1c34b:nodes.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    baseline = types.ModuleType("usability_baseline_nodes")
    baseline.__file__ = str(ROOT / "nodes.py")
    exec(compile(source, "9d1c34b:nodes.py", "exec"), baseline.__dict__)
    return baseline


def test_node_help_all_nodes_describe_every_user_facing_input():
    descriptions = []
    for node_class in nodes.NODE_CLASS_MAPPINGS.values():
        description = getattr(node_class, "DESCRIPTION", "")
        assert isinstance(description, str) and len(description) >= 40
        descriptions.append(description)
        for fields in node_class.INPUT_TYPES().values():
            for value in fields.values():
                assert len(value) > 1
                tooltip = value[1].get("tooltip")
                assert isinstance(tooltip, str) and len(tooltip) >= 20

    help_text = " ".join(descriptions).lower()
    for phrase in (
        "ignored",
        "current-to-previous",
        "0.5",
        "pixel",
        "-1",
        "both depth and motion",
        "experimental",
        "first use",
        "download",
    ):
        assert phrase in help_text


def test_node_help_dlaa_still_uses_the_selected_scale_for_output_dimensions():
    tooltip = nodes.DLSSSuperResolution.INPUT_TYPES()["required"]["quality"][1]["tooltip"]

    assert "DLAA" in tooltip
    assert "scale still controls output dimensions" in tooltip


def test_node_help_easy_controls_explain_inactive_and_bounded_limits():
    schema = nodes.DLSS5EasyPipeline.INPUT_TYPES()["required"]

    assert "ignored for Upscale only" in schema["look"][1]["tooltip"]
    assert "ignored for Upscale only" in schema["effect_strength"][1]["tooltip"]
    assert "currently limited to Upscale + neural rendering" in nodes.DLSS5EasyPipeline.DESCRIPTION


def test_node_help_flashdepth_requires_explicit_environment_paths():
    schema = nodes.DLSS5FlashDepth.INPUT_TYPES()["required"]

    for field in ("flashdepth_python", "flashdepth_repository"):
        tooltip = schema[field][1]["tooltip"].lower()
        assert "leave blank" not in tooltip
        assert "configured default" not in tooltip
        assert "required" in tooltip


def test_node_help_effect_mask_does_not_disable_automatic_masking():
    tooltip = nodes.DLSS5NeuralRendering.INPUT_TYPES()["required"]["auto_mask"][1]["tooltip"].lower()

    assert "independently" in tooltip
    assert "effect_mask" in tooltip


def test_workflow_compatibility_preserves_baseline_contracts_and_groups_nodes():
    baseline = _baseline_nodes()
    assert list(nodes.NODE_CLASS_MAPPINGS) == list(baseline.NODE_CLASS_MAPPINGS)
    assert nodes.NODE_DISPLAY_NAME_MAPPINGS == baseline.NODE_DISPLAY_NAME_MAPPINGS

    for node_id, node_class in nodes.NODE_CLASS_MAPPINGS.items():
        prior = baseline.NODE_CLASS_MAPPINGS[node_id]
        current_contract = _schema_contract(node_class)
        baseline_contract = _schema_contract(prior)
        if node_id == "DLSS5RuntimeSetup":
            current_actions = current_contract["required"]["action"][0]
            baseline_actions = baseline_contract["required"]["action"][0]
            assert current_actions[: len(baseline_actions)] == baseline_actions
            baseline_contract["required"]["action"] = current_contract["required"]["action"]
        assert current_contract == baseline_contract
        assert list(node_class.INPUT_TYPES().keys()) == list(prior.INPUT_TYPES().keys())
        for group in node_class.INPUT_TYPES():
            assert list(node_class.INPUT_TYPES()[group]) == list(prior.INPUT_TYPES()[group])
        assert node_class.RETURN_TYPES == prior.RETURN_TYPES
        assert getattr(node_class, "RETURN_NAMES", None) == getattr(prior, "RETURN_NAMES", None)
        assert node_class.FUNCTION == prior.FUNCTION
        assert node_class.CATEGORY.startswith("Experimental DLSS Bridge")


def test_workflow_compatibility_bundled_workflows_keep_node_inputs_and_widgets():
    for workflow_path in (ROOT / "workflows").glob("*.json"):
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow_nodes = {node["id"]: node for node in workflow["nodes"]}
        for workflow_node in workflow["nodes"]:
            node_class = nodes.NODE_CLASS_MAPPINGS.get(workflow_node["type"])
            if node_class is None:
                continue
            schema = node_class.INPUT_TYPES()
            input_names = set(schema.get("required", {})) | set(schema.get("optional", {}))
            assert all(entry["name"] in input_names for entry in workflow_node["inputs"])
            widgets = [
                (name, value)
                for name, value in schema.get("required", {}).items()
                if not (isinstance(value[0], str) and value[0] in {"IMAGE", "MASK"})
            ]
            values = workflow_node.get("widgets_values", [])
            if not isinstance(values, list):
                continue
            assert len(values) == len(widgets)
            for (_name, (widget_type, options)), saved_value in zip(widgets, values):
                if isinstance(widget_type, list):
                    assert saved_value in widget_type
                elif isinstance(saved_value, (int, float)):
                    assert options.get("min", saved_value) <= saved_value <= options.get("max", saved_value)

        for link_id, source_id, source_slot, target_id, target_slot, link_type in workflow["links"]:
            source = workflow_nodes[source_id]
            target = workflow_nodes[target_id]
            target_input = next(entry for entry in target["inputs"] if entry.get("link") == link_id)
            source_class = nodes.NODE_CLASS_MAPPINGS.get(source["type"])
            target_class = nodes.NODE_CLASS_MAPPINGS.get(target["type"])
            if source_class is not None:
                assert source_class.RETURN_TYPES[source_slot] == link_type
            if target_class is not None:
                target_schema = target_class.INPUT_TYPES()
                expected_type = next(
                    fields[target_input["name"]][0]
                    for fields in target_schema.values()
                    if target_input["name"] in fields
                )
                assert expected_type == link_type


@pytest.fixture
def diagnostic_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(nodes, 'PACKAGE', tmp_path)
    monkeypatch.setattr(nodes, 'PROJECT', tmp_path / 'parent')
    for key in list(os.environ):
        if key.startswith('DLSS5_'):
            monkeypatch.delenv(key)
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    config = {}
    for key in ('python', 'sr_plugin', 'sr_runtime', 'nr_plugin', 'nr_runtime'):
        path = runtime / (key + '.bin')
        path.write_bytes(b'runtime fixture')
        config[key] = str(path)
    (runtime / 'config.json').write_text(json.dumps(config), encoding='utf-8-sig')
    return runtime, config


def _diagnostic_probes(monkeypatch, failure=None):
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        assert 0 < kwargs['timeout'] <= 15
        assert kwargs.get('capture_output')
        if failure and failure in ' '.join(command):
            return subprocess.CompletedProcess(command, 1, '', 'probe failed: ' + failure)
        return subprocess.CompletedProcess(command, 0, 'DLSS_PROBE_OK', '')
    monkeypatch.setattr(nodes.subprocess, 'run', run)
    return commands


def test_runtime_diagnostics_staged_probes_and_ui_contract(monkeypatch, diagnostic_runtime):
    commands = _diagnostic_probes(monkeypatch)
    result = nodes.DLSS5RuntimeStatus().status()
    assert isinstance(result, dict)
    report = result['result'][0]
    assert result['ui']['text'] == [report]
    assert nodes.DLSS5RuntimeStatus.OUTPUT_NODE is True
    for stage in ('Python: PASS', 'VapourSynth import: PASS', 'NumPy import: PASS',
                  'SR plugin load: PASS', 'NR plugin load: PASS', 'Inference: UNTESTED'):
        assert stage in report
    assert 'READY' not in report
    assert any('import numpy' in command[2] for command in commands)
    plugin_commands = [command for command in commands if 'LoadPlugin' in command[2]]
    assert len(plugin_commands) == 2
    assert all('get_frame' not in command[2] for command in commands)
    assert diagnostic_runtime[1]['sr_plugin'] in plugin_commands[-1]
    assert diagnostic_runtime[1]['nr_plugin'] in plugin_commands[-1]


@pytest.mark.parametrize('failure', ['import numpy', 'import vapoursynth', 'LoadPlugin'])
def test_runtime_diagnostics_actionable_dependency_failures(monkeypatch, diagnostic_runtime, failure):
    commands = _diagnostic_probes(monkeypatch, failure)
    report = nodes.DLSS5RuntimeStatus().status()['result'][0]
    assert 'FAIL' in report
    assert 'Inference: UNTESTED' in report
    assert 'selected interpreter' in report if failure.startswith('import') else 'wrapper' in report
    if failure.startswith('import'):
        assert not any('LoadPlugin' in command[2] for command in commands)


@pytest.mark.parametrize('failure', ['timeout', 'launch', 'crash', 'ignored_script'])
def test_runtime_diagnostics_bounded_probe_errors(monkeypatch, diagnostic_runtime, failure):
    def run(command, **kwargs):
        assert 0 < kwargs['timeout'] <= 15
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if failure == 'launch':
            raise OSError('cannot execute')
        if failure == 'ignored_script':
            return subprocess.CompletedProcess(command, 0, '', '')
        return subprocess.CompletedProcess(command, -123, '', '')
    monkeypatch.setattr(nodes.subprocess, 'run', run)
    report = nodes.DLSS5RuntimeStatus().status()['result'][0]
    assert 'Python: FAIL' in report
    assert 'timed out' in report if failure == 'timeout' else 'failed' in report.lower()
    assert 'selected interpreter' in report


def test_runtime_diagnostics_refreshes_config_and_reports_missing_and_lfs(monkeypatch, diagnostic_runtime):
    runtime, config = diagnostic_runtime
    commands = _diagnostic_probes(monkeypatch)
    first = nodes.DLSS5RuntimeStatus.IS_CHANGED()
    assert 'Python: PASS' in nodes.DLSS5RuntimeStatus().status()['result'][0]
    config['python'] = str(runtime / 'missing-python.exe')
    Path(config['nr_plugin']).write_bytes(b'version https://git-lfs.github.com/spec/v1\noid sha256:abc\n')
    Path(config['sr_runtime']).unlink()
    (runtime / 'config.json').write_text(json.dumps(config), encoding='utf-8-sig')
    assert first != nodes.DLSS5RuntimeStatus.IS_CHANGED()
    commands.clear()
    report = nodes.DLSS5RuntimeStatus().status()['result'][0]
    assert 'MISSING' in report and 'LFS POINTER' in report
    assert 'git lfs pull' in report
    assert not commands


def test_runtime_diagnostics_invalid_config_is_displayed(monkeypatch, diagnostic_runtime):
    (diagnostic_runtime[0] / 'config.json').write_text('{', encoding='utf-8')
    result = nodes.DLSS5RuntimeStatus().status()
    assert 'Invalid runtime configuration' in result['ui']['text'][0]
    assert result['result'][0] == result['ui']['text'][0]


def test_runtime_diagnostics_setup_reports_present_files_without_readiness(monkeypatch, diagnostic_runtime):
    runtime, _ = diagnostic_runtime
    for name in ('nvngx_dlss.dll', 'nvngx_dlssnr.dll', 'vsdlssnr.dll', 'vsdlsssr.dll'):
        (runtime / name).write_bytes(b'fixture')
    result = nodes.DLSS5RuntimeSetup().run('Check location', False)
    assert isinstance(result, dict)
    report = result['result'][0]
    assert result['ui']['text'] == [report]
    assert 'PRESENT' in report and 'READY' not in report
    assert 'Runtime Status' in report
    assert nodes.DLSS5RuntimeSetup.IS_CHANGED('Check location', False) != nodes.DLSS5RuntimeSetup.IS_CHANGED('Check location', False)


@pytest.mark.parametrize('operation,stages', [
    ('Upscale only', ('sr',)), ('Neural rendering only', ('nr',)),
    ('Upscale + neural rendering', ('sr', 'nr')),
])
@pytest.mark.parametrize('failure', ['python', 'numpy', 'plugin', None])
def test_early_preflight_only_required_stages_before_models(monkeypatch, diagnostic_runtime, operation, stages, failure):
    runtime, config = diagnostic_runtime
    for unused in {'sr', 'nr'} - set(stages):
        Path(config[unused + '_plugin']).unlink()
        Path(config[unused + '_runtime']).unlink()
    if failure == 'python':
        config['python'] = str(runtime / 'missing-python.exe')
        (runtime / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    commands = _diagnostic_probes(monkeypatch, {'numpy': 'import numpy', 'plugin': 'LoadPlugin'}.get(failure))
    work = []
    image = nodes.torch.zeros(1, 8, 8, 3)
    def estimate(self, *args, **kwargs):
        work.append('model')
        assert any('import numpy' in command[2] for command in commands)
        for stage in stages:
            assert any(config[stage + '_plugin'] in command for command in commands)
        return (image,)
    monkeypatch.setattr(nodes.DLSS5DepthAnythingV2, 'estimate', estimate)
    monkeypatch.setattr(nodes.DLSS5OpticalFlow, 'estimate', estimate)
    def render(self, *args, **kwargs):
        work.append('render')
        return image, 'rendered'
    monkeypatch.setattr(nodes.DLSSSuperResolution, 'upscale', render)
    monkeypatch.setattr(nodes.DLSS5NeuralRendering, 'render', render)
    monkeypatch.setattr(nodes.DLSS5FullPipeline, 'run', render)
    args = (image, 'Still image', operation, '2x', 'Quality', 'Neutral / faithful', 0.85)
    if failure:
        with pytest.raises(RuntimeError, match='preflight'):
            nodes.DLSS5EasyPipeline().run(*args)
        assert work == []
    else:
        output, report = nodes.DLSS5EasyPipeline().run(*args)
        assert output is image and 'rendered' in report
        assert work == ['model', 'model', 'render']
        for unused in {'sr', 'nr'} - set(stages):
            assert not any(config[unused + '_plugin'] in command for command in commands)


@pytest.mark.parametrize('script,passed', [('print(123)', True), ('raise RuntimeError(123)', False)])
def test_runtime_diagnostics_executes_isolated_probe_script(script, passed):
    success, detail = nodes._runtime_probe(Path(sys.executable), script)
    assert success is passed
    assert 'PASS' in detail if passed else '123' in detail


def test_runtime_diagnostics_text_extension_displays_and_refreshes_without_serializing():
    assert (ROOT / 'web' / 'runtime_reports.js').is_file()
    package_source = (ROOT / '__init__.py').read_text(encoding='utf-8')
    assert 'WEB_DIRECTORY' in package_source and './web' in package_source
    script = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
let extension;
globalThis.app = { registerExtension(value) { extension = value; } };
globalThis.document = { createElement() { return { style: {} }; } };
const source = fs.readFileSync('web/runtime_reports.js', 'utf8').replace(/^import .*;$/m, 'const app = globalThis.app;');
await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
for (const name of ['DLSS5RuntimeStatus', 'DLSS5RuntimeSetup']) {
    let originalCalls = 0;
    class Node {
        constructor() { this.widgets = []; this.size = [300, 100]; }
        onExecuted() { originalCalls++; }
        addDOMWidget(name, type, element, options) {
            const widget = { name, type, element, options };
            this.widgets.push(widget);
            return widget;
        }
        setSize(size) { this.size = size; }
        computeSize() { return [300, 220]; }
        setDirtyCanvas() {}
    }
    extension.beforeRegisterNodeDef(Node, { name });
    const node = new Node();
    node.onNodeCreated?.();
    node.onExecuted({ text: ['first result'] });
    assert.equal(node.widgets.length, 1);
    const widget = node.widgets[0];
    assert.equal(widget.element.value, 'first result');
    assert.equal(widget.element.readOnly, true);
    assert.equal(widget.options.serialize, false);
    node.onExecuted({ text: ['updated result', 'line two'] });
    assert.equal(node.widgets.length, 1);
    assert.equal(widget.element.value, 'updated result\nline two');
    assert.equal(originalCalls, 2);
}
class Unrelated {}
extension.beforeRegisterNodeDef(Unrelated, { name: 'OtherNode' });
assert.equal(Unrelated.prototype.onExecuted, undefined);
"""
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
