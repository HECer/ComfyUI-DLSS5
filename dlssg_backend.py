from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import struct
import subprocess
import threading

import numpy as np


SETUP_MAGIC = 0x31534746
SETUP_OUT_MAGIC = 0x31524746
FRAME_MAGIC = 0x31464746
FRAME_OUT_MAGIC = 0x314F4746


def _read_exact(stream, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        block = stream.read(size - len(data))
        if not block:
            raise RuntimeError("The DLSS-G worker closed its output unexpectedly")
        data.extend(block)
    return bytes(data)


def hags_enabled() -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "HwSchMode")
        return int(value) == 2
    except (OSError, ValueError):
        return None


def probe_worker(worker: Path, runtime_dir: Path, timeout: int = 45) -> dict:
    process = subprocess.run(
        [str(worker), "--probe"],
        cwd=str(runtime_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(detail or f"DLSS-G probe exited with {process.returncode}")
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("DLSS-G probe returned no result")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("DLSS-G probe did not return valid JSON") from exc


class DLSSGSession:
    """Persistent binary stream for an external D3D12 DLSS-G worker.

    The protocol follows the public Python client in Merserk/dlss5-visual-enhancer.
    The native worker and NVIDIA runtime are external, user-supplied components.
    """

    def __init__(
        self,
        worker: Path,
        runtime_dir: Path,
        width: int,
        height: int,
        frame_count: int,
        generated_count: int,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.generated_count = int(generated_count)
        self.frame_bytes = self.width * self.height * 4
        self.logs: collections.deque[str] = collections.deque(maxlen=300)
        self.closed = False
        self._next_index = 0
        self.process = subprocess.Popen(
            [str(worker), "--serve"],
            cwd=str(runtime_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._log_thread = threading.Thread(target=self._read_logs, daemon=True)
        self._log_thread.start()
        try:
            self.process.stdin.write(
                struct.pack(
                    "<5I",
                    SETUP_MAGIC,
                    self.width,
                    self.height,
                    max(1, int(frame_count)),
                    self.generated_count,
                )
            )
            self.process.stdin.flush()
            magic, status, maximum, _reserved = struct.unpack(
                "<4I", _read_exact(self.process.stdout, struct.calcsize("<4I"))
            )
            if magic != SETUP_OUT_MAGIC or status:
                raise RuntimeError(
                    f"DLSS-G session creation failed with status {status}; "
                    f"runtime maximum is {maximum + 1}x\n{self.log_text()}"
                )
            if self.generated_count > maximum:
                raise RuntimeError(
                    f"Requested {self.generated_count} generated frames, but the "
                    f"runtime maximum is {maximum}"
                )
            self.maximum = int(maximum)
        except Exception:
            self.close()
            raise

    def _read_logs(self) -> None:
        assert self.process.stderr is not None
        for raw in iter(self.process.stderr.readline, b""):
            self.logs.append(raw.decode("utf-8", "replace").rstrip())

    def log_text(self) -> str:
        return "\n".join(self.logs)

    def process_frame(
        self,
        rgba: np.ndarray,
        motion: np.ndarray,
        timestamp_numerator: int,
        timestamp_denominator: int,
        *,
        reset: bool,
    ) -> list[np.ndarray]:
        if self.closed:
            raise RuntimeError("DLSS-G session is closed")
        color = np.ascontiguousarray(rgba, dtype=np.uint8)
        vectors = np.ascontiguousarray(motion, dtype=np.float16)
        if color.shape != (self.height, self.width, 4):
            raise ValueError(f"Unexpected DLSS-G color shape: {color.shape}")
        if vectors.shape != (self.height, self.width, 2):
            raise ValueError(f"Unexpected DLSS-G motion shape: {vectors.shape}")
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(
            struct.pack(
                "<4I2q",
                FRAME_MAGIC,
                self._next_index,
                int(reset),
                0,
                int(timestamp_numerator),
                int(timestamp_denominator),
            )
        )
        self.process.stdin.write(memoryview(color).cast("B"))
        self.process.stdin.write(memoryview(vectors).cast("B"))
        self.process.stdin.flush()
        frame_index = self._next_index
        self._next_index += 1
        magic, status, generated, disabled = struct.unpack(
            "<4I", _read_exact(self.process.stdout, struct.calcsize("<4I"))
        )
        if magic != FRAME_OUT_MAGIC or status:
            raise RuntimeError(
                f"DLSS-G failed at input frame {frame_index} with status {status}\n"
                f"{self.log_text()}"
            )
        if disabled:
            return []
        if generated > self.generated_count:
            raise RuntimeError(
                f"DLSS-G returned {generated} frames; expected at most "
                f"{self.generated_count}"
            )
        return [
            np.frombuffer(_read_exact(self.process.stdout, self.frame_bytes), np.uint8)
            .reshape(self.height, self.width, 4)
            .copy()
            for _ in range(generated)
        ]

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        process = self.process
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        self._log_thread.join(timeout=1)

    def __enter__(self) -> "DLSSGSession":
        return self

    def __exit__(self, *_args) -> None:
        self.close()
