"""Isolated VapourSynth runner for official NVIDIA DLSS Super Resolution."""

import argparse
from pathlib import Path
import numpy as np
import vapoursynth as vs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--depth", required=True)
    p.add_argument("--mvec", required=True)
    p.add_argument("--plugin", required=True)
    p.add_argument("--scale", type=int, required=True)
    p.add_argument("--quality", type=int, required=True)
    a = p.parse_args()
    color = np.load(a.input, mmap_mode="r")
    depth = np.load(a.depth, mmap_mode="r")
    motion = np.load(a.mvec, mmap_mode="r")
    count, h, w, _ = color.shape
    if depth.shape != (count, h, w) or motion.shape != (count, h, w, 2):
        raise ValueError("guide dimensions must match input")
    core = vs.core
    if not hasattr(core, "dlsssr"):
        core.std.LoadPlugin(path=str(Path(a.plugin).resolve()))
    blank = core.std.BlankClip(
        width=w, height=h, length=count, format=vs.RGBS, color=[0.0, 0.0, 0.0]
    )
    db = core.std.BlankClip(
        width=w, height=h, length=count, format=vs.GRAYS, color=[0.0]
    )
    mb = core.std.BlankClip(
        width=w, height=h, length=count, format=vs.RGBS, color=[0.0, 0.0, 0.0]
    )

    def uc(n, f):
        o = f.copy()
        for q in range(3):
            np.asarray(o[q])[:, :w] = color[n, :, :, q]
        return o

    def ud(n, f):
        o = f.copy()
        np.asarray(o[0])[:, :w] = depth[n]
        return o

    def um(n, f):
        o = f.copy()
        np.asarray(o[0])[:, :w] = motion[n, :, :, 0]
        np.asarray(o[1])[:, :w] = motion[n, :, :, 1]
        return o

    source = core.std.ModifyFrame(blank, blank, uc)
    z = core.std.ModifyFrame(db, db, ud)
    mv = core.std.ModifyFrame(mb, mb, um)
    up = core.dlsssr.Upscale(source, depth=z, mvec=mv, scale=a.scale, quality=a.quality)
    ow, oh = w * a.scale, h * a.scale
    result = np.lib.format.open_memmap(
        a.output, mode="w+", dtype=np.float32, shape=(count, oh, ow, 3)
    )
    for i in range(count):
        f = up.get_frame(i)
        for q in range(3):
            result[i, :, :, q] = np.clip(np.asarray(f[q])[:, :ow], 0.0, 1.0)
    result.flush()


if __name__ == "__main__":
    main()
