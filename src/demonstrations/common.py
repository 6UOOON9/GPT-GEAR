"""Reference file boundaries, strict JSON and shared numeric validation; stdlib only."""
import hashlib
import json
import math
from pathlib import Path


class ReferenceError(ValueError):
    pass


REFERENCE_MODALITIES = (
    ("images",), ("text",), ("images", "text"),
    ("text", "trajectory"), ("images", "trajectory"), ("images", "text", "trajectory"),
)


def reference_modalities(*, video=None, text=None, trajectory=None):
    """Return canonical modalities; an empty selection means references disabled."""
    if trajectory is not None and video is None and text is None:
        raise ReferenceError("--trajectory requires --reference-video or --reference-text")
    return [name for name, value in (
        ("images", video), ("text", text), ("trajectory", trajectory)
    ) if value is not None]


def reference_enabled(args):
    return bool(reference_modalities(
        video=getattr(args, "reference_video", None),
        text=getattr(args, "reference_text", None),
        trajectory=getattr(args, "trajectory", None),
    ))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_file(directory, filename):
    """Sources must be contained regular files, not traversal or symlink aliases."""
    if not isinstance(filename, str) or not filename or Path(filename).is_absolute() or ".." in Path(filename).parts:
        raise ReferenceError("invalid relative source filename")
    path = directory / filename
    if path.resolve() != path or not path.is_relative_to(directory) or not path.is_file():
        raise ReferenceError("unsafe or missing reference source file")
    return path


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def strict_json(raw):
    def reject_constant(value):
        raise ReferenceError("non-finite JSON value: " + value)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceError("duplicate JSON key: " + key)
            result[key] = value
        return result

    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_sequence(metadata, records):
    count = metadata.get('frames')
    if type(count) is not int or count < 1 or not isinstance(records, list) or len(records) != count:
        raise ReferenceError('trajectory record count disagrees with reference')
    fps = metadata.get('fps')
    if not finite_number(fps) or fps <= 0:
        raise ReferenceError('invalid trajectory reference fps')
    return count


def validate_frame(record, index, *, extra_fields=()):
    if (not isinstance(record, dict) or set(record) != {'frame_index', 'action', *extra_fields}
            or type(record['frame_index']) is not int or record['frame_index'] != index):
        raise ReferenceError('trajectory frame indices must be consecutive from zero')


def validate_vector(value, size, name):
    if not isinstance(value, list) or len(value) != size or not all(map(finite_number, value)):
        raise ReferenceError('invalid trajectory ' + name)


def validate_delta(action):
    validate_vector(action['dpos'], 3, 'dpos')
    validate_vector(action['dquat'], 4, 'dquat')
    # Four-decimal rounding changes a unit quaternion's norm by at most 1e-4.
    # Validate without normalizing or rewriting the source values.
    if not math.isclose(math.hypot(*action['dquat']), 1.0, rel_tol=0.0, abs_tol=1e-4):
        raise ReferenceError('trajectory dquat must be a unit quaternion')


def read_text(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")
    if not text.strip() or "\x00" in text:
        raise ReferenceError("reference text must be nonempty UTF-8 without NUL")
    return raw, text


def checked_cache_file(directory, filename):
    if not isinstance(filename, str):
        raise ReferenceError("invalid cached reference filename")
    path = directory / filename
    if path.resolve() != path or path.parent != directory or not path.is_file():
        raise ReferenceError("unsafe or missing cached reference file")
    return path
