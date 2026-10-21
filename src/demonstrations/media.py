"""Independent RGB view discovery, frame sampling, decoding and image validation."""
import argparse
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import re
import shutil
import subprocess

from execution.runtime import thread_environment
from .common import ReferenceError, checked_cache_file, finite_number, sha256_file, source_file, strict_json


def positive_fps(value):
    try:
        fps = float(value)
    except (TypeError, ValueError, OverflowError):
        raise argparse.ArgumentTypeError("FPS must be a finite positive number") from None
    if not math.isfinite(fps) or fps <= 0:
        raise argparse.ArgumentTypeError("FPS must be a finite positive number")
    return fps


def frame_indices(timestamps, mode, fps=1.0):
    """Sample the first source frame at/after each relative FPS tick, plus the end.

    Advance over ticks arithmetically rather than allocating one entry per tick:
    even a sampling rate much higher than the source rate costs O(source frames).
    Decimal fractions avoid dropping exact tick boundaries through float rounding.
    """
    if not timestamps:
        raise ReferenceError("reference requires at least one decoded frame")
    if mode not in ("endpoints", "sequence"):
        raise ReferenceError("unknown reference mode")
    if not finite_number(fps) or fps <= 0:
        raise ReferenceError("reference-fps must be a finite positive number")
    previous = None
    for timestamp in timestamps:
        if not finite_number(timestamp) or (previous is not None and timestamp < previous):
            raise ReferenceError("reference timestamps must be finite and ordered")
        previous = timestamp
    if mode == "endpoints":
        return sorted({0, len(timestamps) - 1})
    origin, rate = Fraction(str(timestamps[0])), Fraction(str(fps))
    indices, next_tick = [0], 1
    for index, timestamp in enumerate(timestamps[1:], 1):
        reached_tick = (Fraction(str(timestamp)) - origin) * rate
        reached_tick = reached_tick.numerator // reached_tick.denominator
        if reached_tick >= next_tick:
            indices.append(index)
            next_tick = reached_tick + 1
    if indices[-1] != len(timestamps) - 1:
        indices.append(len(timestamps) - 1)
    return indices


def run_media(command, timeout):
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, check=False,
            env=thread_environment()
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReferenceError(f"media preparation failed: {type(exc).__name__}") from None
    # At loglevel error, stderr is a decoding error, even if the program exits 0.
    if result.returncode or result.stderr.strip():
        raise ReferenceError("media validation/decoding failed: " + result.stderr[-1500:].strip())
    return result.stdout


def camera_names(cameras):
    if (
        not isinstance(cameras, list)
        or not cameras
        or any(not isinstance(c, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", c) is None for c in cameras)
        or len(set(cameras)) != len(cameras)
    ):
        raise ReferenceError("camera names must be unique safe identifiers")
    return cameras


def scan_videos(directory, benchmark="robodojo"):
    directory = Path(directory).expanduser().resolve(strict=True)
    if not (directory / 'videos.json').exists():
        videos = {}
        cameras = {'robodojo': tuple((name, name + '.mp4') for name in ('head', 'left_wrist', 'right_wrist')),
                   'libero-geomotion': (('agentview', 'agentview.mp4'), ('robot0_eye_in_hand', 'wrist.mp4')),
                   'libero-plus': (('agentview', 'agentview.mp4'), ('robot0_eye_in_hand', 'wrist.mp4')),
                   'robotwin': tuple((name, name + '.mp4') for name in ('head_camera', 'left_camera', 'right_camera')),
                   'robocasa-gr1': (('egoview', 'egoview.mp4'),),
                   'univtac': (('head', 'head.mp4'), ('wrist', 'wrist.mp4'))}[benchmark]
        for camera, suffix in cameras:
            matches = [p for p in directory.iterdir() if p.name.endswith(suffix) and p.is_file()]
            if len(matches) != 1:
                raise ReferenceError(f'{suffix}: expected exactly one video')
            videos[camera] = source_file(directory, matches[0].name)
        return videos
    manifest = strict_json(source_file(directory, "videos.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") not in ("sim-reference-videos-v1", "robodojo-reference-videos-v1")
        or not isinstance(manifest.get("videos"), dict)
    ):
        raise ReferenceError("videos.json must declare sim-reference-videos-v1 or robodojo-reference-videos-v1 and videos")
    camera_names(list(manifest["videos"]))
    return {camera: source_file(directory, filename) for camera, filename in manifest["videos"].items()}


def _decode_view(video, destination, camera, *, mode, fps, timeout):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ReferenceError("references require ffmpeg and ffprobe on PATH")
    fingerprint = sha256_file(video)
    info = strict_json(
        run_media(
            [
                ffprobe,
                "-v",
                "error",
                "-err_detect",
                "explode",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=width,height,best_effort_timestamp_time:format=format_name",
                "-of",
                "json",
                str(video),
            ],
            timeout,
        )
    )
    if "mp4" not in info.get("format", {}).get("format_name", "").split(","):
        raise ReferenceError("reference video is not an MP4 container")
    frames = info.get("frames", [])
    if not frames:
        raise ReferenceError("reference video has no decoded frames")
    width, height = frames[0].get("width"), frames[0].get("height")
    if type(width) is not int or type(height) is not int or min(width, height) < 1:
        raise ReferenceError("invalid reference video dimensions")
    timestamps = []
    for frame in frames:
        if (frame.get("width"), frame.get("height")) != (width, height):
            raise ReferenceError("reference video dimensions changed")
        try:
            timestamps.append(float(frame["best_effort_timestamp_time"]))
        except (KeyError, ValueError, TypeError):
            raise ReferenceError("reference frame has no usable timestamp") from None
    indices = frame_indices(timestamps, mode, fps)
    selection = "+".join(f"eq(n,{index})" for index in indices)
    run_media(
        [
            ffmpeg,
            "-hide_banner",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-xerror",
            "-err_detect",
            "explode",
            "-noautorotate",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-vf",
            f"format=rgb24,select='{selection}'",
            "-vsync",
            "0",
            "-c:v",
            "png",
            "-threads:v",
            "1",
            "-start_number",
            "0",
            str(destination / f"{camera}-%06d.png"),
        ],
        timeout,
    )
    if sha256_file(video) != fingerprint:
        raise ReferenceError("source reference video changed during decoding")
    records = []
    for ordinal, index in enumerate(indices):
        path = destination / f"{camera}-{ordinal:06d}.png"
        raw = path.read_bytes()
        if (
            raw[:8] != b"\x89PNG\r\n\x1a\n"
            or int.from_bytes(raw[16:20], "big") != width
            or int.from_bytes(raw[20:24], "big") != height
        ):
            raise ReferenceError("decoded PNG dimensions do not match the video")
        records.append(
            dict(
                frame_index=index,
                timestamp_seconds=timestamps[index],
                relative_timestamp_seconds=timestamps[index] - timestamps[0],
                label=(
                    "reference_start"
                    if index == 0
                    else "reference_end"
                    if index == len(frames) - 1
                    else "reference_frame"
                ),
                images=[
                    dict(camera=camera, file=path.name, sha256=hashlib.sha256(raw).hexdigest(), shape=[height, width])
                ],
            )
        )
    if len(list(destination.glob(f"{camera}-*.png"))) != len(indices):
        raise ReferenceError("decoded image count disagrees with selected frames")
    return records, dict(
        file=str(video), sha256=fingerprint, shape=[height, width], total_frames=len(frames), sampled_indices=indices
    )


def prepare_images(video, destination, *, mode="sequence", fps=1.0, timeout=600.0, benchmark="robodojo"):
    """Camera-major order; each view has its own timestamps and frame indices."""
    videos = scan_videos(video, benchmark)
    frame_indices([0.0, 1.0], mode, fps)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    frames, sources = [], {}
    for camera, path in videos.items():
        records, sources[camera] = _decode_view(path, destination, camera, mode=mode, fps=fps, timeout=timeout)
        frames.extend(records)
    return dict(
        frames=frames,
        sources=sources,
        mode=mode,
        requested_fps=fps if mode == "sequence" else None,
        actual_num_frames=len(frames),
        image_count=len(frames),
        camera_order=list(videos),
    )


def image_labels(manifest):
    """Shared attachment ordering/labels for offline text and online delivery."""
    for frame in manifest["frames"]:
        for image in frame["images"]:
            yield (
                image,
                dict(
                    label=frame["label"],
                    frame_index=frame["frame_index"],
                    timestamp_seconds=frame["timestamp_seconds"],
                    camera=image["camera"],
                    shape=image["shape"],
                    source="reference_video",
                ),
            )


def validate_images(directory, manifest):
    cameras = camera_names(manifest.get("camera_order"))
    if (
        manifest.get("mode") not in ("endpoints", "sequence")
        or manifest["camera_order"] != cameras
        or manifest["image_count"] != len(manifest["frames"])
        or not manifest["frames"]
    ):
        raise ReferenceError("invalid reference image configuration")
    if manifest["mode"] == "sequence":
        positive_fps(manifest["requested_fps"])
    previous = {c: -1 for c in cameras}
    times = {c: -math.inf for c in cameras}
    order = []
    for frame in manifest["frames"]:
        if len(frame["images"]) != 1:
            raise ReferenceError("independent reference frames must have one view")
        image = frame["images"][0]
        camera, index, timestamp = image["camera"], frame["frame_index"], frame["timestamp_seconds"]
        if camera not in cameras or type(index) is not int or index <= previous[camera]:
            raise ReferenceError("invalid reference camera/frame order")
        if not finite_number(timestamp) or timestamp < times[camera]:
            raise ReferenceError("invalid reference timestamps")
        previous[camera], times[camera] = index, timestamp
        order.append(cameras.index(camera))
        path = checked_cache_file(directory, image["file"])
        raw = path.read_bytes()
        if (
            path.suffix != ".png"
            or hashlib.sha256(raw).hexdigest() != image["sha256"]
            or raw[:8] != b"\x89PNG\r\n\x1a\n"
            or image["shape"] != [int.from_bytes(raw[20:24], "big"), int.from_bytes(raw[16:20], "big")]
        ):
            raise ReferenceError("cached reference image changed")
    if order != sorted(order) or set(order) != set(range(len(cameras))):
        raise ReferenceError("invalid reference camera ordering")
