"""Worker lifecycle and cached-clip behavior without native runtimes or downloads."""
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    assert (ROOT / filename).exists(), f"Missing worker feature: {filename}"
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def session(monkeypatch, tmp_path):
    module = load("worker_session_test", "native_session.py")
    server = tmp_path / "server.py"
    server.write_text('''import json,os,sys,time
for line in sys.stdin:
    request=json.loads(line); mode=request['command'][-1]
    print('DLSS_PROGRESS 1 2',flush=True)
    if mode=='hang':
        print('native timeout diagnostic',file=sys.stderr,flush=True)
        time.sleep(30)
    if mode=='crash': os._exit(7)
    result={'ok':mode!='error','pid':os.getpid(),'reused':True,'error':'deliberate failure' if mode=='error' else ''}
    print('DLSS_RESULT '+request['id']+' '+json.dumps(result),flush=True)
''', encoding="utf-8")
    monkeypatch.setattr(module, "WORKER_SCRIPT", server)
    monkeypatch.setattr(module, "SESSION_TEMP_ROOT", tmp_path)
    yield module
    module.close_workers()


def run(session, mode="ok", **kwargs):
    return session.run_worker([sys.executable, str(ROOT / "sr_bridge_runner.py"), mode], **kwargs)


def payload(result):
    line = next(line for line in result.stdout.splitlines() if line.startswith("DLSS_RESULT "))
    return json.loads(line.split(" ", 2)[2])


def test_repeated_requests_reuse_one_process_and_close_resources(session, tmp_path):
    first, second = run(session), run(session)
    assert first.returncode == second.returncode == 0
    assert payload(first)["pid"] == payload(second)["pid"]
    session.close_workers()
    assert not list(tmp_path.glob("dlss-worker-*"))


def test_timeout_discards_worker_and_next_request_starts_fresh(session):
    first = payload(run(session))["pid"]
    with pytest.raises(__import__("subprocess").TimeoutExpired) as caught:
        run(session, "hang", timeout=0.15)
    assert "DLSS_PROGRESS" in caught.value.output
    assert "native timeout diagnostic" in caught.value.stderr
    assert payload(run(session))["pid"] != first


def test_cancellation_discards_worker_after_real_progress(session):
    first = payload(run(session))["pid"]

    def progress(value, total):
        assert (value, total) == (1, 2)
        raise RuntimeError("Comfy cancelled")

    with pytest.raises(RuntimeError, match="Comfy cancelled"):
        run(session, "hang", progress=progress)
    assert payload(run(session))["pid"] != first


@pytest.mark.parametrize("mode", ["error", "crash"])
def test_failed_requests_do_not_retain_poisoned_worker(session, mode):
    first = payload(run(session))["pid"]
    result = run(session, mode)
    assert result.returncode != 0
    assert "failure" in result.stderr or "exit" in result.stderr
    assert payload(run(session))["pid"] != first


def test_cache_refreshes_arrays_without_leaking_old_frames(monkeypatch, tmp_path):
    # The real worker shares the runners' graph construction and output code.
    monkeypatch.setitem(sys.modules, "vapoursynth", types.SimpleNamespace(core=None))
    worker = load("native_worker_test", "native_worker.py")
    builds, clears, requested = [], [], []

    def build(inputs, args):
        assert args.disable_frame_cache, "Mutable input clips must not retain cached frames"
        builds.append(args.quality)
        def graph(n):
            requested.append(n)
            return inputs["color"][n] + .125
        return graph

    def load_inputs(args):
        return {"color": np.load(args.input), "depth": None, "motion": None}, 2

    def write_output(graph, output, count, original_count):
        np.save(output, np.stack([graph(i) for i in range(count)]))

    import argparse
    def parser():
        p = argparse.ArgumentParser()
        p.add_argument("input"); p.add_argument("output")
        p.add_argument("--quality", type=int, default=2)
        p.add_argument("--scale", type=int, default=2)
        p.add_argument("--plugin", default="plugin")
        return p

    module = types.SimpleNamespace(argument_parser=parser, load_inputs=load_inputs,
                                   build_clip=build, write_output=write_output)
    monkeypatch.setattr(worker, "NR", module)
    monkeypatch.setattr(worker, "CORE", types.SimpleNamespace(clear_cache=lambda: clears.append(True)))
    cache = {}
    source, output = tmp_path / "input.npy", tmp_path / "output.npy"
    command = ["python", "bridge_runner.py", str(source), str(output)]
    for value in (0., 1.):
        np.save(source, np.full((2, 2, 3, 3), value, np.float32))
        response = worker.execute(command, cache)
        np.testing.assert_allclose(np.load(output), value + .125)
    assert response["reused"] and builds == [2]
    assert requested == [0, 1, 0, 1] and len(clears) >= 2
    worker.execute(command + ["--quality", "1"], cache)
    assert builds == [2, 1] and len(cache) == 1


def test_runtime_changes_restart_worker_instead_of_reusing_loaded_plugin(session,tmp_path):
    plugin=tmp_path/"plugin.dll"
    plugin.write_bytes(b"first")
    command=[sys.executable,str(ROOT/"bridge_runner.py"),"--plugin",str(plugin),"ok"]
    first=payload(session.run_worker(command))["pid"]
    assert payload(session.run_worker(command))["pid"]==first
    plugin.write_bytes(b"second version")
    assert payload(session.run_worker(command))["pid"]!=first
