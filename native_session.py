"""Serialized, cancellable ownership of the optional persistent native helper."""
import atexit
from contextlib import suppress
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

WORKER_SCRIPT = Path(__file__).with_name("native_worker.py")
SESSION_TEMP_ROOT = None
_lock = threading.Lock()
_worker = None


def _close():
    global _worker
    if _worker is None:
        return
    process, directory, out, err, _ = _worker
    _worker = None
    try:
        if process.poll() is None:
            with suppress(ProcessLookupError):
                process.kill()
        process.wait()
    finally:
        with suppress(OSError, ValueError):
            process.stdin.close()
        out.close()
        err.close()
        shutil.rmtree(directory, ignore_errors=True)


def _tail(path):
    with open(path, "rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 8192))
        return stream.read(8192).decode("utf-8", errors="replace")


def _identity(command):
    files = [WORKER_SCRIPT, Path(command[1])]
    for flag in ("--plugin", "--snippet"):
        if flag in command:
            files.append(Path(command[command.index(flag) + 1]))
    signatures = []
    for path in files:
        metadata = path.stat() if path.exists() else None
        signatures.append((str(path.resolve()), None if metadata is None else
                           (metadata.st_mtime_ns, metadata.st_size)))
    return command[0], tuple(signatures)


def close_workers():
    with _lock:
        _close()


def run_worker(command, timeout=None, check_cancel=None, progress=None):
    """Run the original runner command, retaining initialization between requests."""
    global _worker
    started = time.monotonic()
    def checkpoint():
        if check_cancel:
            check_cancel()
        if timeout is not None and time.monotonic() - started >= timeout:
            raise subprocess.TimeoutExpired(command, timeout)
    while not _lock.acquire(timeout=.05):
        checkpoint()
    try:
        checkpoint()
        identity = _identity(command)
        if _worker and (_worker[0].poll() is not None or _worker[4] != identity
                        or _worker[2].tell() > 8 * 1024 * 1024):
            _close()
        if _worker is None:
            directory = Path(tempfile.mkdtemp(prefix="dlss-worker-", dir=SESSION_TEMP_ROOT))
            out = open(directory / "stdout.log", "w+b", buffering=0)
            err = open(directory / "stderr.log", "w+b", buffering=0)
            try:
                process = subprocess.Popen([command[0], "-u", str(WORKER_SCRIPT)],
                    stdin=subprocess.PIPE, stdout=out, stderr=err, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except BaseException:
                out.close(); err.close()
                shutil.rmtree(directory, ignore_errors=True)
                raise
            _worker = (process, directory, out, err, identity)
        process, directory, out, err, _ = _worker
        request_id = uuid.uuid4().hex
        with open(directory / "stdout.log", "r", encoding="utf-8", errors="replace") as reader, \
             open(directory / "stderr.log", "r", encoding="utf-8", errors="replace") as errors:
            reader.seek(0, 2); errors.seek(0, 2)
            process.stdin.write(json.dumps({"id": request_id, "command": command}) + "\n")
            process.stdin.flush()
            stdout = pending = ""
            while True:
                checkpoint()
                pending += reader.read()
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    stdout = (stdout + line + "\n")[-8192:]
                    if line.startswith("DLSS_PROGRESS ") and progress:
                        parts = line.split()
                        progress(int(parts[1]), int(parts[2]))
                    prefix = "DLSS_RESULT " + request_id + " "
                    if line.startswith(prefix):
                        result = json.loads(line[len(prefix):])
                        stderr = errors.read()[-8192:]
                        if not result["ok"]:
                            stderr += "\n" + result.get("error", "Native worker failure")
                            reader.close(); errors.close()
                            _close()
                        return subprocess.CompletedProcess(command, 0 if result["ok"] else 1, stdout, stderr)
                if process.poll() is not None:
                    stderr = errors.read()[-8192:] + f"\nNative worker exit {process.returncode}"
                    reader.close(); errors.close()
                    _close()
                    return subprocess.CompletedProcess(command, 1, stdout, stderr)
                time.sleep(.02)
    except subprocess.TimeoutExpired as exc:
        if _worker is not None:
            exc.output = _tail(_worker[1] / "stdout.log")
            exc.stderr = _tail(_worker[1] / "stderr.log")
        _close()
        raise
    except BaseException:
        _close()
        raise
    finally:
        _lock.release()


atexit.register(close_workers)
