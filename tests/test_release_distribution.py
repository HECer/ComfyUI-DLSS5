"""Distribution contracts: publish real binaries and exclude local agent/test state."""
from pathlib import Path

import shutil
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_registry_checkout_materializes_lfs_before_publish():
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish_action.yml").read_text())
    steps = workflow["jobs"]["publish-node"]["steps"]
    checkouts = [s for s in steps if s.get("uses", "").startswith("actions/checkout@")]
    assert checkouts and all(s.get("with", {}).get("lfs") is True for s in checkouts), "Registry archives must contain the real LFS runtime, not its pointer"
    assert not any(s.get("uses", "").startswith("Comfy-Org/publish-node-action@") for s in steps), "The composite publisher performs a second checkout without LFS"
    assert any("node publish" in s.get("run", "") for s in steps)


def test_registry_archive_excludes_development_state_and_keeps_workers(tmp_path):
    # The registry uses gitignore syntax; exercise Git itself without extra test dependencies.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copyfile(ROOT / ".comfyignore", tmp_path / ".gitignore")

    def excluded(name):
        result = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "--no-index", name], capture_output=True)
        assert result.returncode in (0, 1), result.stderr.decode()
        return result.returncode == 0
    for name in (".agents/context/PROJECT.md", ".codex/hooks.json", ".yoke/context/PROJECT.md", ".pytest-tmp/test_registration/account.json", ".context/ships/log.jsonl", "tests/test_native_worker.py"):
        assert excluded(name), f"Development state would ship in registry archive: {name}"
    for name in ("__init__.py", "nodes.py", "depth_backend.py", "native_worker.py", "native_session.py", "bridge_runner.py", "sr_bridge_runner.py", "runtime/nvngx_dlssnr.dll", "runtime/nvngx_dlss.dll", "runtime/vsdlssnr.dll", "runtime/vsdlsssr.dll", "web/runtime_reports.js"):
        assert not excluded(name), f"Required runtime file excluded: {name}"
