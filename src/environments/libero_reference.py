"""Validator for existing LIBERO single-arm reference packages."""
from demonstrations.common import (
    ReferenceError, finite_number, validate_sequence, validate_frame, validate_delta,
)

TRAJECTORY_FORMAT = 'libero-codex-trajectory-v1'
ANNOTATION_CAMERAS = ('agentview', 'robot0_eye_in_hand')

# Exact semantics published by scripts/replay_hdf5.py's v1 exporter.
ACTION_SEMANTICS = dict(
    meaning='current frame to next frame; last frame is null',
    dpos='p[t+1] - p[t], metres in environment axes',
    dquat='q[t+1] * inverse(q[t]), shortest relative wxyz rotation, left multiplication',
    gripper='actions[t,6]: -1=open, +1=close; null for gaps or unknown commands',
    execution='reference only; execution parameters are chosen by the consumer',
)
def validate_trajectory(metadata, records):
    """Validate complete sequence semantics, without assuming frame-aligned videos."""
    if not isinstance(metadata, dict) or metadata.get('format') != TRAJECTORY_FORMAT:
        raise ReferenceError('unsupported trajectory reference format')
    pose = metadata.get('pose')
    expected_pose = dict(reference='robot0_grip_site', coordinate_frame='environment',
                         position_unit='metre', quaternion_order='wxyz')
    if not isinstance(pose, dict) or any(pose.get(k) != v for k, v in expected_pose.items()):
        raise ReferenceError('unsupported trajectory pose semantics')
    action = metadata.get('action')
    if not isinstance(action, dict) or any(action.get(k) != v for k, v in ACTION_SEMANTICS.items()):
        raise ReferenceError('unsupported trajectory action semantics')
    count = validate_sequence(metadata, records)
    for index, record in enumerate(records):
        validate_frame(record, index)
        action = record['action']
        if index == count - 1:
            if action is not None:
                raise ReferenceError('last trajectory action must be null')
            continue
        if not isinstance(action, dict) or set(action) != {'dpos', 'dquat', 'gripper'}:
            raise ReferenceError('invalid trajectory action')
        validate_delta(action)
        if action['gripper'] not in ('open', 'close', None):
            raise ReferenceError('invalid trajectory gripper')
    sampling = metadata.get('sampling')
    if not isinstance(sampling, dict) or not isinstance(sampling.get('video'), str):
        raise ReferenceError('missing trajectory sampling metadata')
    dt = sampling.get('nominal_sample_interval_seconds')
    if (dt is None and count != 1) or (dt is not None and (not finite_number(dt) or dt <= 0)):
        raise ReferenceError('invalid trajectory sample interval')
    gaps = sampling.get('sampling_gaps')
    unknown = sampling.get('unknown_gripper_action_frames')
    if not isinstance(gaps, list) or not isinstance(unknown, list):
        raise ReferenceError('invalid trajectory sampling gaps or unknown gripper frames')
    expected_unknown = [i for i, r in enumerate(records[:-1]) if r['action']['gripper'] is None]
    if any(type(i) is not int for i in unknown) or unknown != expected_unknown:
        raise ReferenceError('unknown gripper frames disagree with trajectory')
    previous = -1
    for gap in gaps:
        if not isinstance(gap, dict):
            raise ReferenceError('invalid trajectory sampling gap')
        start, end, interval = gap.get('from_frame'), gap.get('to_frame'), gap.get('interval_seconds')
        if (type(start) is not int or type(end) is not int or not previous < start < count - 1
                or end != start + 1 or not finite_number(interval) or interval <= 0 or start not in unknown):
            raise ReferenceError('invalid trajectory sampling gap')
        previous = start
