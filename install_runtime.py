from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request


RELEASE = "nightly-2026-08-31"
ARCHIVE = "Vapourkit-windows-nightly-2026-08-31.7z"
URL = f"https://github.com/Kim2091/vapourkit-nightly/releases/download/{RELEASE}/{ARCHIVE}"
SHA256 = "af3ecfb868a96477ab10e1588d7bac0fb2729332f2f464b998677efdee9e0554"
NVIDIA_DLSS_RELEASE = "v310.7.0"
NVIDIA_DLSS_URL = (
    "https://raw.githubusercontent.com/NVIDIA/DLSS/"
    f"{NVIDIA_DLSS_RELEASE}/lib/Windows_x86_64/rel/nvngx_dlss.dll"
)
NVIDIA_DLSS_SHA256 = "be6e434a94ca32499515eb62ca0e6c274526055d568d0426e4c652dcdfb6ee6e"
NVIDIA_DLSSNR_SHA256 = "8270b350cd82de5ce89806872cdd6b6a9249b80836b91bbeb3573470744cc206"
NVIDIA_DLSSG_SHA256 = "c64928fdb7c48a57722ea8eef2662171edc323473adea66c29a206a23f1a2bed"
DLSSG_WORKER_RELEASE = "v0.1.0"
DLSSG_WORKER_URL = (
    "https://github.com/HECer/DLSSG-Stream-Worker/releases/download/"
    f"{DLSSG_WORKER_RELEASE}/dlssg-worker.exe"
)
DLSSG_WORKER_SHA256 = "e0d4c76c231f0cf4ea24bedb0a83ebde7bb982098f484f5134a6cc17168265c4"
DLSSG_LEGACY_WORKER_SHA256 = {
    "9e8110801dafbcd4b9f3b9b2e3c38fd9bd2036cbb0335d95ca993ecd1ef6fb79"
}
PACKAGE = Path(__file__).resolve().parent
RUNTIME = PACKAGE / "runtime"
BUNDLED_PLUGINS = ("vsdlssnr.dll", "vsdlsssr.dll")


def load_runtime_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid runtime configuration at {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"Invalid runtime configuration at {path}: expected a JSON object")
    return config


def write_runtime_config(path: Path, config: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, label: str = "file") -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(
        url, headers={"User-Agent": "ComfyUI-DLSS5-runtime-installer/0.1"}
    )
    with urllib.request.urlopen(request) as response, partial.open("wb") as output:
        total = int(response.headers.get("Content-Length", "0"))
        received = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
            received += len(block)
            if total:
                print(
                    f"\rDownloading {label}: {received * 100 / total:5.1f}%",
                    end="",
                    flush=True,
                )
    print()
    partial.replace(destination)


def find_one(root: Path, name: str) -> Path:
    matches = sorted(root.rglob(name))
    if not matches:
        raise RuntimeError(f"{name} was not found in the extracted VapourKit build")
    return matches[0]


def bundled_plugin(name: str) -> Path:
    if name not in BUNDLED_PLUGINS:
        raise ValueError(f"Unsupported bundled plugin: {name}")
    path = RUNTIME / name
    if not path.is_file():
        raise RuntimeError(
            f"Bundled {name} is missing from the extension package: {path}"
        )
    return path


def stage_bundled_plugins(destination: Path) -> tuple[Path, Path]:
    """Ensure the project wrappers are present in the local runtime directory."""
    destination.mkdir(parents=True, exist_ok=True)
    staged = []
    for name in BUNDLED_PLUGINS:
        target = destination / name
        source = bundled_plugin(name)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        staged.append(target)
    return staged[0], staged[1]


def install_sr_runtime(destination: Path) -> str:
    """Install the pinned official NVIDIA SR runtime into the local runtime dir."""
    if destination.is_file():
        actual = sha256(destination).lower()
        if actual != NVIDIA_DLSS_SHA256:
            raise RuntimeError(
                "Existing NVIDIA DLSS SR runtime has an unexpected SHA-256. "
                f"Preserve or replace it manually: {destination}\nSHA-256: {actual}"
            )
        return actual

    print(f"Pinned NVIDIA DLSS SR runtime: {NVIDIA_DLSS_URL}")
    download(NVIDIA_DLSS_URL, destination, "NVIDIA DLSS SR runtime")
    actual = sha256(destination).lower()
    if actual != NVIDIA_DLSS_SHA256:
        destination.rename(destination.with_suffix(destination.suffix + ".unverified"))
        raise RuntimeError(
            "NVIDIA DLSS SR runtime SHA-256 mismatch: "
            f"expected {NVIDIA_DLSS_SHA256}, got {actual}"
        )
    return actual


def verify_runtime_hash(destination: Path, expected: str, label: str) -> str:
    if not destination.is_file():
        raise RuntimeError(f"Bundled {label} is missing: {destination}")
    actual = sha256(destination).lower()
    if actual != expected:
        raise RuntimeError(
            f"Bundled {label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def find_vapour_python(root: Path) -> Path:
    for candidate in sorted(root.rglob("python.exe")):
        result = subprocess.run(
            [str(candidate), "-c", "import vapoursynth"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return candidate
    raise RuntimeError("No VapourSynth-capable python.exe was found in VapourKit")


def install_dlssg_worker(destination: Path) -> str:
    if destination.is_file():
        current = sha256(destination).lower()
        if current == DLSSG_WORKER_SHA256:
            return current
        if current not in DLSSG_LEGACY_WORKER_SHA256:
            raise RuntimeError(
                "Existing DLSS-G worker has an unknown SHA-256. Preserve or remove "
                f"it manually before retrying: {destination}\nSHA-256: {current}"
            )
        backup = destination.with_name(
            f"dlssg-worker.legacy-{current[:8]}.exe"
        )
        if backup.exists():
            raise RuntimeError(f"Legacy worker backup already exists: {backup}")
        destination.replace(backup)
        print(f"Preserved legacy DLSS-G worker: {backup}")
    print(f"Pinned open-source DLSS-G worker: {DLSSG_WORKER_URL}")
    download(DLSSG_WORKER_URL, destination, "DLSS-G worker")
    actual = sha256(destination).lower()
    if actual != DLSSG_WORKER_SHA256:
        destination.rename(destination.with_suffix(".exe.unverified"))
        raise RuntimeError(
            "DLSS-G worker SHA-256 mismatch: "
            f"expected {DLSSG_WORKER_SHA256}, got {actual}"
        )
    return actual


def install() -> str:
    try:
        import py7zr
    except ImportError as exc:
        raise RuntimeError(
            "py7zr is missing. Install/update this node through ComfyUI Manager first."
        ) from exc

    config_path = RUNTIME / "config.json"
    config = load_runtime_config(config_path)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    dlssg_dir = RUNTIME / "dlssg"
    dlssg_dir.mkdir(exist_ok=True)
    dlssg_worker = dlssg_dir / "dlssg-worker.exe"
    worker_hash = install_dlssg_worker(dlssg_worker)
    print("DLSS-G worker SHA-256 verified.")

    neural_runtime = RUNTIME / "nvngx_dlssnr.dll"
    if not neural_runtime.is_file():
        raise RuntimeError(
            f"Bundled nvngx_dlssnr.dll is missing from the extension package:\n{neural_runtime}"
        )

    sr_runtime = RUNTIME / "nvngx_dlss.dll"
    sr_runtime_hash = install_sr_runtime(sr_runtime)
    print("NVIDIA DLSS SR runtime SHA-256 verified.")
    neural_runtime_hash = verify_runtime_hash(
        neural_runtime, NVIDIA_DLSSNR_SHA256, "NVIDIA DLSS NR runtime"
    )
    dlssg_runtime = dlssg_dir / "nvngx_dlssg.dll"
    dlssg_runtime_hash = verify_runtime_hash(
        dlssg_runtime, NVIDIA_DLSSG_SHA256, "NVIDIA DLSS-G runtime"
    )

    archive = RUNTIME / ARCHIVE
    if not archive.is_file():
        print(f"Pinned source: {URL}")
        download(URL, archive, "VapourKit")
    actual = sha256(archive)
    if actual.lower() != SHA256:
        raise RuntimeError(
            f"VapourKit archive SHA-256 mismatch: expected {SHA256}, got {actual}"
        )
    print("VapourKit archive SHA-256 verified.")

    extracted = RUNTIME / RELEASE
    marker = extracted / ".extracted-ok"
    if not marker.is_file():
        if extracted.exists():
            raise RuntimeError(
                f"Incomplete extraction exists at {extracted}; rename it and retry"
            )
        extracted.mkdir(parents=True)
        with py7zr.SevenZipFile(archive, mode="r") as bundle:
            bundle.extractall(path=extracted)
        marker.write_text(SHA256 + "\n", encoding="utf-8")

    # VapourKit supplies the VapourSynth Python runtime.  The project wrappers
    # and the pinned NVIDIA SR runtime live together in the local runtime dir;
    # the SR wrapper uses its module directory as the NGX search path.
    nr_plugin, sr_plugin = stage_bundled_plugins(RUNTIME)
    python = find_vapour_python(extracted)
    config.update({
        "python": str(python.resolve()),
        "nr_plugin": str(nr_plugin.resolve()),
        "nr_runtime": str(neural_runtime.resolve()),
        "nvidia_dlssnr_sha256": neural_runtime_hash,
        "sr_plugin": str(sr_plugin.resolve()),
        "sr_runtime": str(sr_runtime.resolve()),
        "vapourkit_release": RELEASE,
        "vapourkit_archive_sha256": SHA256,
        "nvidia_dlss_release": NVIDIA_DLSS_RELEASE,
        "nvidia_dlss_sha256": sr_runtime_hash,
        "dlssg_runtime": str(dlssg_runtime.resolve()),
        "dlssg_runtime_sha256": dlssg_runtime_hash,
        "dlssg_worker": str(dlssg_worker.resolve()),
        "dlssg_worker_release": DLSSG_WORKER_RELEASE,
        "dlssg_worker_sha256": DLSSG_WORKER_SHA256,
    })
    config.setdefault("temp_dir", str((RUNTIME / "temp").resolve()))
    config.setdefault("timeout_seconds", 0)
    Path(config["temp_dir"]).mkdir(exist_ok=True)
    write_runtime_config(config_path, config)
    return (
        "Runtime setup complete. Restart ComfyUI, then run DLSS 5 Runtime Status.\n"
        f"Configuration: {RUNTIME / 'config.json'}\n"
        f"Bundled wrappers: {nr_plugin.name}, {sr_plugin.name}\n"
        f"Bundled NVIDIA runtimes: {neural_runtime.name}, {sr_runtime.name}\n"
        f"Verified NVIDIA DLSS SR SHA-256: {sr_runtime_hash}\n"
        f"Verified VapourKit SHA-256: {SHA256}"
        f"\nVerified DLSS-G worker SHA-256: {DLSSG_WORKER_SHA256}"
    )


def main() -> int:
    try:
        print(install())
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
