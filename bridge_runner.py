"""Isolated VapourSynth runner used by the ComfyUI node."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import vapoursynth as vs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--snippet", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--depth")
    parser.add_argument("--mvec")
    args = parser.parse_args()

    frames = np.load(args.input, mmap_mode="r")
    if frames.ndim != 4 or frames.shape[-1] != 3:
        raise ValueError("input must have shape [frames,height,width,3]")
    settings = json.loads(args.settings)
    original_count, height, width, _ = frames.shape
    # A two-frame clip lets a still image take the same initialized path as video.
    if original_count == 1:
        frames = np.concatenate((frames, frames), axis=0)
    depth_frames = motion_frames = None
    if args.depth or args.mvec:
        if not args.depth or not args.mvec:
            raise ValueError("depth and mvec must be supplied together")
        depth_frames = np.load(args.depth, mmap_mode="r")
        motion_frames = np.load(args.mvec, mmap_mode="r")
        if original_count == 1:
            depth_frames = np.concatenate((depth_frames, depth_frames), axis=0)
            motion_frames = np.concatenate((motion_frames, motion_frames), axis=0)
        if depth_frames.shape != (
            len(frames),
            height,
            width,
        ) or motion_frames.shape != (len(frames), height, width, 2):
            raise ValueError("guide dimensions must match color [frames,height,width]")

    core = vs.core
    if not hasattr(core, "dlssnr"):
        core.std.LoadPlugin(path=str(Path(args.plugin).resolve()))
    blank = core.std.BlankClip(
        width=width,
        height=height,
        length=len(frames),
        format=vs.RGBS,
        color=[0.0, 0.0, 0.0],
    )

    def upload(n: int, f: vs.VideoFrame) -> vs.VideoFrame:
        out = f.copy()
        for plane in range(3):
            np.asarray(out[plane])[:, :width] = frames[n, :, :, plane]
        return out

    source = core.std.ModifyFrame(blank, blank, upload)
    kwargs = dict(
        snippet=str(Path(args.snippet).resolve()),
        style=int(settings["style"]),
        style_strength=float(settings["style_strength"]),
        intensity=float(settings["intensity"]),
        local_structure=float(settings["local_structure"]),
        skin_structure=float(settings["skin_structure"]),
        auto_mask=int(settings["auto_mask"]),
        preset=int(settings.get("preset", 0)),
        feature_id=int(settings.get("feature_id", 18)),
        bypass_caller_check=1,
    )
    if depth_frames is not None:
        depth_blank = core.std.BlankClip(
            width=width, height=height, length=len(frames), format=vs.GRAYS, color=[0.0]
        )
        motion_blank = core.std.BlankClip(
            width=width,
            height=height,
            length=len(frames),
            format=vs.RGBS,
            color=[0.0, 0.0, 0.0],
        )

        def upload_depth(n: int, f: vs.VideoFrame) -> vs.VideoFrame:
            out = f.copy()
            np.asarray(out[0])[:, :width] = depth_frames[n]
            return out

        def upload_motion(n: int, f: vs.VideoFrame) -> vs.VideoFrame:
            out = f.copy()
            np.asarray(out[0])[:, :width] = motion_frames[n, :, :, 0]
            np.asarray(out[1])[:, :width] = motion_frames[n, :, :, 1]
            return out

        kwargs.update(
            depth=core.std.ModifyFrame(depth_blank, depth_blank, upload_depth),
            mvec=core.std.ModifyFrame(motion_blank, motion_blank, upload_motion),
            depth_inverted=int(settings.get("depth_inverted", False)),
            mvec_scale_x=float(settings.get("mvec_scale_x", 1.0)),
            mvec_scale_y=float(settings.get("mvec_scale_y", 1.0)),
        )
    enhanced = core.dlssnr.Enhance(source, **kwargs)
    result = np.lib.format.open_memmap(
        args.output, mode="w+", dtype=np.float32, shape=(len(frames), height, width, 3)
    )
    for index in range(len(frames)):
        frame = enhanced.get_frame(index)
        for plane in range(3):
            result[index, :, :, plane] = np.clip(
                np.asarray(frame[plane])[:, :width], 0.0, 1.0
            )
    if original_count == 1:
        single = np.asarray(result[-1:]).copy()
        del result
        np.save(args.output, single)
    else:
        result.flush()


if __name__ == "__main__":
    main()
