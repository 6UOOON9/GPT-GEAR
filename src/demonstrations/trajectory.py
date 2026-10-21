"""Benchmark-specific trajectory dispatch and lossless reference packaging."""
import hashlib
from pathlib import Path

from .common import ReferenceError, compact_json, sha256_file, source_file, strict_json

TRAJECTORY_FORMATS = {'robodojo': 'robodojo-codex-trajectory-v1', 'libero-plus': 'libero-codex-trajectory-v1',
                      'libero-geomotion': 'libero-codex-trajectory-v1',
                      'robocasa-gr1': 'robocasa-gr1-trajectory-v1', 'univtac': 'univtac-codex-trajectory-v2',
                      'robotwin': 'robotwin-codex-dual-trajectory-v1'}


def trajectory_module(format):
    from importlib import import_module
    from environments import environment_package
    for benchmark, supported in TRAJECTORY_FORMATS.items():
        if format == supported:
            return import_module(environment_package(benchmark) + '.reference')
    return None


def validate_trajectory(metadata, records):
    if not isinstance(metadata, dict):
        raise ReferenceError('invalid trajectory metadata')
    module = trajectory_module(metadata.get('format'))
    if module is None:
        raise ReferenceError('unsupported trajectory reference format')
    return module.validate_trajectory(metadata, records)


def prepare_trajectory(descriptor, destination):
    descriptor = Path(descriptor).expanduser().resolve(strict=True)
    descriptor_raw = descriptor.read_bytes()
    source = strict_json(descriptor_raw)
    if not isinstance(source, dict) or not isinstance(source.get("files"), dict):
        raise ReferenceError("invalid trajectory descriptor")
    filename = source["files"].get("trajectory")
    if not isinstance(filename, str) or not filename:
        raise ReferenceError("missing trajectory file in descriptor")
    path = source_file(descriptor.parent, filename)
    raw = path.read_bytes()
    records = [strict_json(line) for line in raw.decode("utf-8").splitlines()]
    # Do not expose source paths, validation/ground-truth results or arbitrary report fields.
    metadata = {key: source.get(key) for key in ("format", "frames", "fps", "pose", "action", "sampling")}
    if source.get('format') == 'univtac-codex-trajectory-v2':
        metadata['robot_state'] = source.get('robot_state')
    validate_trajectory(metadata, records)
    module = trajectory_module(metadata['format'])
    semantics = module.ACTION_SEMANTICS
    pose_fields = ("reference", "coordinate_frame", "position_unit", "quaternion_order")
    if metadata["format"] == "robotwin-codex-dual-trajectory-v1":
        pose_fields += ("arms", "initial_poses", "final_poses")
    metadata["pose"] = {
        k: metadata["pose"][k] for k in pose_fields
    }
    metadata["action"] = {k: metadata["action"][k] for k in semantics}
    metadata["sampling"] = {
        k: metadata["sampling"][k]
        for k in ("nominal_sample_interval_seconds", "sampling_gaps", "unknown_gripper_action_frames", "unknown_hand_action_frames", "video") if k in metadata["sampling"]
    }
    # Preserve every validated JSONL number's original spelling/precision, not a
    # float round-trip. Record keys are already strictly whitelisted above.
    header = compact_json(dict(source="reference_trajectory", metadata=metadata))
    encoded = (header[:-1] + ',"records":[' + ",".join(raw.decode("utf-8").splitlines()) + "]}").encode("utf-8")
    descriptor_hash = hashlib.sha256(descriptor_raw).hexdigest()
    trajectory_hash = hashlib.sha256(raw).hexdigest()
    if sha256_file(descriptor) != descriptor_hash or sha256_file(path) != trajectory_hash:
        raise ReferenceError("source trajectory changed during reference preparation")
    cached = Path(destination) / "trajectory.json"
    cached.write_bytes(encoded)
    return dict(
        file=cached.name,
        sha256=hashlib.sha256(encoded).hexdigest(),
        text_bytes=len(encoded),
        record_count=len(records),
        source_descriptor=str(descriptor),
        descriptor_sha256=descriptor_hash,
        source_trajectory=str(path),
        source_sha256=trajectory_hash,
    )


def check_correspondence(trajectory, videos):
    """Check file identity only, not temporal alignment or text correctness."""
    descriptor = Path(trajectory).expanduser().resolve(strict=True)
    source = strict_json(descriptor.read_bytes())
    files = source.get("files", {}).get("videos") if isinstance(source, dict) else None
    if files is None and isinstance(source, dict) and source.get('format') in (
            'robocasa-gr1-trajectory-v1', 'univtac-codex-trajectory-v2', 'robotwin-codex-dual-trajectory-v1'):
        files = {camera: source.get('files', {}).get(camera) for camera in videos}
    if not isinstance(files, dict) or set(files) != set(videos):
        raise ReferenceError("trajectory descriptor must identify every reference video")
    for camera, filename in files.items():
        if sha256_file(source_file(descriptor.parent, filename)) != sha256_file(videos[camera]):
            raise ReferenceError("trajectory descriptor does not correspond to reference video")
