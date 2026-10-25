"""VapourSynth helper; one cached graph per native stage, no Torch dependency."""
import json
import importlib.util
from pathlib import Path
import queue
import sys
import threading
import traceback

import vapoursynth as vs


def _runner(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NR = _runner("bridge_runner")

CORE = vs.core


def execute(command, cache):
    stage = Path(command[1]).name
    if stage != "bridge_runner.py":
        raise ValueError("SR feature reuse is disabled: independent-sequence equivalence failed")
    runner = NR
    args = runner.argument_parser().parse_args(command[2:])
    args.disable_frame_cache = True
    inputs, original_count = runner.load_inputs(args)
    # File names change each request; graph settings and tensor shapes must not.
    settings = {k: v for k, v in vars(args).items() if k not in ("input", "output", "depth", "mvec")}
    key = (tuple((k, None if v is None else (v.shape, str(v.dtype))) for k, v in inputs.items()),
           json.dumps(settings, sort_keys=True))
    CORE.clear_cache()
    entry = cache.get(stage)
    reused = entry is not None and entry[0] == key
    if not reused:
        cache.pop(stage, None)
        entry = None  # Release the previous NGX feature before creating its replacement.
        holder = dict(inputs)
        entry = (key, holder, runner.build_clip(holder, args))
        cache[stage] = entry
    else:
        entry[1].update(inputs)
    try:
        # Starting at zero also resets the native filter's temporal history.
        runner.write_output(entry[2], args.output, len(inputs["color"]), original_count)
    finally:
        CORE.clear_cache()
        entry[1].clear()
        for array in inputs.values():
            mapping = getattr(array, "_mmap", None)
            if mapping is not None:
                mapping.close()
    return {"ok": True, "reused": reused}


def main():
    requests = queue.Queue()
    def read():
        for line in sys.stdin:
            requests.put(line)
        requests.put(None)
    threading.Thread(target=read, daemon=True).start()
    cache = {}
    while True:
        try:
            line = requests.get(timeout=120)
        except queue.Empty:
            return
        if line is None:
            return
        request = json.loads(line)
        try:
            response = execute(request["command"], cache)
        except BaseException:
            cache.clear()
            response = {"ok": False, "error": traceback.format_exc()}
        print("DLSS_RESULT " + request["id"] + " " + json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
