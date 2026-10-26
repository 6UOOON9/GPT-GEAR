"""Prepare and verify the reference cache delivered to an evaluation episode."""
import hashlib
from pathlib import Path
import time

from environments.benchmarks import BENCHMARKS
from .common import ReferenceError, checked_cache_file, compact_json, read_text, sha256_file, strict_json
from .common import REFERENCE_MODALITIES, reference_modalities
from .media import prepare_images, scan_videos, validate_images
from .trajectory import TRAJECTORY_FORMATS, check_correspondence, prepare_trajectory, validate_trajectory

FORMAT = "sim-reference-v1"
TOOL = "read_reference"
DIRECTORY = "reference"
MANIFEST = "manifest.json"


def prepare(video, destination, *, trajectory=None, text=None, mode="sequence", fps=1.0, timeout=600.0, benchmark="robodojo", max_frames=None):
    """Image sampling never touches the complete trajectory. No text provenance claim."""
    started = time.monotonic()
    modalities = reference_modalities(video=video, trajectory=trajectory, text=text)
    if not modalities:
        raise ReferenceError("at least one of --reference-video or --reference-text is required")
    if benchmark not in BENCHMARKS:
        raise ReferenceError('unknown reference benchmark')
    if trajectory is not None:
        expected = TRAJECTORY_FORMATS[benchmark]
        if strict_json(Path(trajectory).read_bytes()).get('format') != expected:
            raise ReferenceError('reference trajectory does not match benchmark')
    text_raw = read_text(text)[0] if text is not None else None
    if video is not None and trajectory is not None:
        check_correspondence(trajectory, scan_videos(video, benchmark))
    destination = Path(destination)
    if video is not None:
        manifest = prepare_images(video, destination, mode=mode, fps=fps, timeout=timeout,
                                  benchmark=benchmark, max_frames=max_frames)
        if max_frames is not None:
            manifest['max_frames'] = max_frames
    else:
        destination.mkdir(parents=True, exist_ok=False)
        manifest = dict(frames=[], actual_num_frames=0, image_count=0, camera_order=[])
    manifest.update(
        format=FORMAT, benchmark=benchmark,
        modalities=modalities,
    )
    if trajectory is not None:
        manifest["trajectory"] = prepare_trajectory(trajectory, destination)
        if sha256_file(trajectory) != manifest["trajectory"]["descriptor_sha256"]:
            raise ReferenceError("trajectory descriptor changed during preparation")
        if video is not None:
            check_correspondence(trajectory, scan_videos(video, benchmark))
            for source in manifest["sources"].values():
                if sha256_file(source["file"]) != source["sha256"]:
                    raise ReferenceError("source video changed during preparation")
    if text is not None:
        raw, _ = read_text(text)
        if raw != text_raw:
            raise ReferenceError("source reference text changed during preparation")
        cached = destination / "reference_steps.txt"
        cached.write_bytes(raw)
        manifest["text"] = dict(
            file=cached.name,
            sha256=hashlib.sha256(raw).hexdigest(),
            text_bytes=len(raw),
            source_text=str(Path(text).resolve()),
            semantic_review="not_verified",
            provenance="operator_selected_not_automatically_proven",
        )
    manifest["preparation_seconds"] = time.monotonic() - started
    (destination / MANIFEST).write_text(compact_json(manifest) + "\n", encoding="utf-8")
    return manifest


def cache_directory(output):
    return Path(output).resolve() / DIRECTORY


def load_text(output, manifest):
    info = manifest["text"]
    raw, text = read_text(checked_cache_file(cache_directory(output), info["file"]))
    if len(raw) != info["text_bytes"] or hashlib.sha256(raw).hexdigest() != info["sha256"]:
        raise ReferenceError("cached reference text changed")
    return text


def load_trajectory(output, manifest):
    info = manifest["trajectory"]
    path = checked_cache_file(cache_directory(output), info["file"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != info["sha256"] or len(raw) != info["text_bytes"]:
        raise ReferenceError("cached reference trajectory changed")
    payload = strict_json(raw)
    if not isinstance(payload, dict) or payload.get("source") != "reference_trajectory":
        raise ReferenceError("invalid cached trajectory payload")
    expected = TRAJECTORY_FORMATS[manifest['benchmark']]
    if payload['metadata'].get('format') != expected:
        raise ReferenceError('cached trajectory benchmark mismatch')
    validate_trajectory(payload["metadata"], payload["records"])
    if len(payload["records"]) != info["record_count"]:
        raise ReferenceError("cached trajectory count changed")
    return raw.decode("utf-8")


def load_manifest(output, expected_sha256=None):
    directory = cache_directory(output)
    path = checked_cache_file(directory, MANIFEST)
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise ReferenceError("cached reference manifest changed")
    manifest = strict_json(path.read_bytes())
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise ReferenceError("invalid cached reference manifest")
    if manifest.get('benchmark') not in BENCHMARKS:
        raise ReferenceError('invalid reference benchmark')
    modalities = manifest.get("modalities")
    if not isinstance(modalities, list) or tuple(modalities) not in REFERENCE_MODALITIES:
        raise ReferenceError("invalid cached reference modalities")
    if ("trajectory" in modalities) != ("trajectory" in manifest):
        raise ReferenceError("cached reference modalities disagree")
    if ("text" in modalities) != ("text" in manifest):
        raise ReferenceError("cached reference text modalities disagree")
    if "text" in modalities:
        load_text(output, manifest)
    if "trajectory" in modalities:
        load_trajectory(output, manifest)
    frames = manifest.get("frames")
    if not isinstance(frames, list) or len(frames) != manifest.get("actual_num_frames"):
        raise ReferenceError("invalid cached reference frames")
    if "images" not in modalities:
        if frames or manifest.get("image_count") != 0 or manifest.get("camera_order") != []:
            raise ReferenceError("unexpected images in reference cache without images")
        return manifest
    validate_images(directory, manifest)
    return manifest


def output_token_limit(output):
    """Conservative text budget for direct MCP output, including image labels.

    Image blocks do not consume Codex's per-tool truncation budget. Keep text
    headroom without treating encoded image bytes as tokens; transport and
    model-context limits are enforced separately.
    """
    manifest = load_manifest(output)
    size = len(compact_json(manifest).encode("utf-8")) + 16384
    if "text" in manifest:
        size += manifest["text"]["text_bytes"]
    if "trajectory" in manifest:
        size += manifest["trajectory"]["text_bytes"]
    size += manifest["image_count"] * 1024
    return size * 2  # JSON escaping and MCP envelope headroom; never round trajectory values.
