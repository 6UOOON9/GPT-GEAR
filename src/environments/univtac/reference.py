"""Reference semantics adapted from astra-as-policy; see NOTICE."""
from demonstrations.common import (
    ReferenceError, finite_number, validate_sequence, validate_frame, validate_delta,
)

TRAJECTORY_FORMAT = 'univtac-codex-trajectory-v2'
ANNOTATION_CAMERAS = ('head', 'wrist')

ACTION_SEMANTICS = dict(
    meaning='current frame to next frame; last frame is null',
    dpos='p[t+1] - p[t], metres in robot_base axes',
    dquat='q[t+1] * inverse(q[t]), shortest relative wxyz rotation, left multiplication',
    gripper_position_m='recorded panda_finger_joint1 at next frame; absolute symmetric finger target in metres',
    execution='reference only; execution parameters are chosen by the consumer',
)

ROBOT_STATE_SEMANTICS = dict(
    joint_positions='original embodiment/joint columns 0:7; panda_joint1 through panda_joint7; radians',
    gripper_position_m='original embodiment/joint column 7; measured panda_finger_joint1 in metres; not total jaw gap',
)

def validate_trajectory(metadata, records):
    """Validate complete sequence semantics, without assuming frame-aligned videos."""
    if not isinstance(metadata, dict) or metadata.get('format') != TRAJECTORY_FORMAT:
        raise ReferenceError('unsupported trajectory reference format')
    if metadata.get('robot_state') != ROBOT_STATE_SEMANTICS:
        raise ReferenceError('unsupported original joint-state semantics')
    pose = metadata.get('pose')
    expected_pose = dict(reference='gripper_center', coordinate_frame='robot_base',
                         position_unit='metre', quaternion_order='wxyz')
    if not isinstance(pose, dict) or any(pose.get(k) != v for k, v in expected_pose.items()):
        raise ReferenceError('unsupported trajectory pose semantics')
    action = metadata.get('action')
    if not isinstance(action, dict) or any(action.get(k) != v for k, v in ACTION_SEMANTICS.items()):
        raise ReferenceError('unsupported trajectory action semantics')
    count = validate_sequence(metadata, records)
    for index, record in enumerate(records):
        validate_frame(record, index, extra_fields=('robot_state',))
        state = record['robot_state']
        if not isinstance(state, dict) or set(state) != {'joint_positions', 'gripper_position_m'}:
            raise ReferenceError('invalid original robot state')
        joints = state['joint_positions']
        if not isinstance(joints, list) or len(joints) != 7 or not all(map(finite_number, joints)):
            raise ReferenceError('invalid original arm joints')
        g = state['gripper_position_m']
        if not finite_number(g) or not 0 <= g <= 0.04:
            raise ReferenceError('invalid recorded gripper_position_m')
        action = record['action']
        if index == count - 1:
            if action is not None:
                raise ReferenceError('last trajectory action must be null')
            continue
        if not isinstance(action, dict) or set(action) != {'dpos', 'dquat', 'gripper_position_m'}:
            raise ReferenceError('invalid trajectory action')
        validate_delta(action)
        g = action['gripper_position_m']
        if not finite_number(g) or not 0 <= g <= 0.04:
            raise ReferenceError('invalid trajectory gripper_position_m')
    for i, record in enumerate(records[:-1]):
        if record['action']['gripper_position_m'] != records[i+1]['robot_state']['gripper_position_m']:
            raise ReferenceError('gripper target must match next original recorded joint position')
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
    if unknown:
        raise ReferenceError('unknown gripper frames disagree with trajectory')
    previous = -1
    for gap in gaps:
        if not isinstance(gap, dict):
            raise ReferenceError('invalid trajectory sampling gap')
        start, end, interval = gap.get('from_frame'), gap.get('to_frame'), gap.get('interval_seconds')
        if (type(start) is not int or type(end) is not int or not previous < start < count - 1
                or end != start + 1 or not finite_number(interval) or interval <= 0):
            raise ReferenceError('invalid trajectory sampling gap')
        previous = start
