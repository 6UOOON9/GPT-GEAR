"""Reference semantics adapted from astra-as-policy; see NOTICE."""
from demonstrations.common import (
    ReferenceError, finite_number, validate_sequence, validate_frame, validate_delta, validate_vector,
)

TRAJECTORY_FORMAT = 'robocasa-gr1-trajectory-v1'
ANNOTATION_CAMERAS = ('egoview',)

ACTION_SEMANTICS = dict(
    meaning='current frame to next frame; last frame is null',
    dpos='p[t+1] - p[t], metres in environment axes',
    dquat='q[t+1] * inverse(q[t]), shortest relative wxyz rotation, left multiplication',
    hand='actions[t]: six raw radian position targets per hand; pinky, ring, middle, index, thumb flexion, thumb rotation',
    execution='reference only; execution parameters are chosen by the consumer',
)

def validate_trajectory(metadata, records):
    """Validate complete sequence semantics, without assuming frame-aligned videos."""
    if not isinstance(metadata, dict) or metadata.get('format') != TRAJECTORY_FORMAT:
        raise ReferenceError('unsupported trajectory reference format')
    pose = metadata.get('pose')
    expected_pose = dict(reference={'right': 'gripper0_right_grip_site', 'left': 'gripper0_left_grip_site'}, coordinate_frame='environment',
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
        if not isinstance(action, dict) or set(action) != {'arms'} or set(action['arms']) != {'right', 'left'}:
            raise ReferenceError('invalid dual-arm trajectory action')
        for part in action['arms'].values():
            if not isinstance(part, dict) or set(part) != {'dpos', 'dquat', 'hand'}:
                raise ReferenceError('invalid arm trajectory action')
            validate_delta(part)
            validate_vector(part['hand'], 6, 'hand')
            if any(abs(x) > 3 for x in part['hand']):
                raise ReferenceError('invalid raw hand target')
    sampling = metadata.get('sampling')
    if not isinstance(sampling, dict) or not isinstance(sampling.get('video'), str):
        raise ReferenceError('missing trajectory sampling metadata')
    dt = sampling.get('nominal_sample_interval_seconds')
    if (dt is None and count != 1) or (dt is not None and (not finite_number(dt) or dt <= 0)):
        raise ReferenceError('invalid trajectory sample interval')
    gaps = sampling.get('sampling_gaps')
    unknown = sampling.get('unknown_hand_action_frames')
    if not isinstance(gaps, list) or not isinstance(unknown, list):
        raise ReferenceError('invalid trajectory sampling gaps or unknown hand frames')
    expected_unknown = []
    if any(type(i) is not int for i in unknown) or unknown != expected_unknown:
        raise ReferenceError('unknown hand frames disagree with trajectory')
    previous = -1
    for gap in gaps:
        if not isinstance(gap, dict):
            raise ReferenceError('invalid trajectory sampling gap')
        start, end, interval = gap.get('from_frame'), gap.get('to_frame'), gap.get('interval_seconds')
        if (type(start) is not int or type(end) is not int or not previous < start < count - 1
                or end != start + 1 or not finite_number(interval) or interval <= 0 or start not in unknown):
            raise ReferenceError('invalid trajectory sampling gap')
        previous = start
