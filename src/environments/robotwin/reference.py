"""RoboTwin reference semantics adapted from robotwin_eval_clean_20261019.zip; see NOTICE."""
import math
from demonstrations.common import (
    ReferenceError, finite_number, validate_sequence, validate_frame, validate_delta,
)

TRAJECTORY_FORMAT = "robotwin-codex-dual-trajectory-v1"
ANNOTATION_CAMERAS = ('head_camera', 'left_camera', 'right_camera')
ANNOTATION_IMAGE_LIMIT = 42

ACTION_SEMANTICS = dict(
    meaning='current frame to next frame; last frame is null',
    dpos='p[t+1] - p[t], metres in environment axes',
    dquat='q[t+1] * inverse(q[t]), shortest relative wxyz rotation, left multiplication',
    gripper='null: source contains measured opening, not verified open/close command; gripper_opening records measurements in [0,1]',
    execution='reference only; execution parameters are chosen by the consumer',
)

def validate_trajectory(metadata, records):
    """Validate complete sequence semantics, without assuming frame-aligned videos."""
    if not isinstance(metadata, dict) or metadata.get('format') != TRAJECTORY_FORMAT:
        raise ReferenceError('unsupported trajectory reference format')
    pose = metadata.get('pose')
    expected_pose = dict(reference='robotwin_native_ee', coordinate_frame='environment',
                         position_unit='metre', quaternion_order='wxyz')
    if not isinstance(pose, dict) or any(pose.get(k) != v for k, v in expected_pose.items()):
        raise ReferenceError('unsupported trajectory pose semantics')
    if pose.get('arms') != ['left', 'right']:
        raise ReferenceError('both trajectory arms are required')
    for field in ('initial_poses', 'final_poses'):
        endpoints = pose.get(field)
        if not isinstance(endpoints, dict) or set(endpoints) != {'left', 'right'}:
            raise ReferenceError('missing trajectory endpoint poses')
        for values in endpoints.values():
            if (not isinstance(values, list) or len(values) != 7 or not all(map(finite_number, values))
                    or not math.isclose(math.hypot(*values[3:]), 1., abs_tol=1e-4)):
                raise ReferenceError('invalid trajectory endpoint pose')
    action = metadata.get('action')
    if not isinstance(action, dict) or any(action.get(k) != v for k, v in ACTION_SEMANTICS.items()):
        raise ReferenceError('unsupported trajectory action semantics')
    count = validate_sequence(metadata, records)
    for index, record in enumerate(records):
        validate_frame(record, index, extra_fields=('gripper_opening',))
        opening = record['gripper_opening']
        if (not isinstance(opening, dict) or set(opening) != {'left', 'right'}
                or any(not finite_number(value) or not 0 <= value <= 1 for value in opening.values())):
            raise ReferenceError('invalid measured gripper opening')
        action = record['action']
        if index == count - 1:
            if action is not None:
                raise ReferenceError('last trajectory action must be null')
            continue
        if not isinstance(action, dict) or set(action) != {'left', 'right'}:
            raise ReferenceError('both trajectory actions are required')
        for arm_action in action.values():
            if not isinstance(arm_action, dict) or set(arm_action) != {'dpos', 'dquat', 'gripper'}:
                raise ReferenceError('invalid trajectory action')
            validate_delta(arm_action)
            if arm_action['gripper'] is not None:
                raise ReferenceError('source gripper commands are unknown; do not infer them from measurements')
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
    expected_unknown = [index for index, record in enumerate(records[:-1])
                        if any(action['gripper'] is None for action in record['action'].values())]
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

