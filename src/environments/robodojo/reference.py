"""Validate measured bimanual RoboDojo reference trajectories."""
import math
from demonstrations.common import (
    ReferenceError, finite_number, validate_sequence, validate_frame, validate_delta,
)

TRAJECTORY_FORMAT = "robodojo-codex-trajectory-v1"
ANNOTATION_CAMERAS = ('head', 'left_wrist', 'right_wrist')

ACTION_SEMANTICS = dict(
    meaning="current frame to next frame; last frame is null",
    dpos="p[t+1] - p[t], metres in environment axes",
    dquat="q[t+1] * inverse(q[t]), shortest relative wxyz rotation, left multiplication",
    gripper="per-arm target: 0=closed, 1=open, [0,1]; null=unknown, not hold",
    execution="reference only; execution parameters are chosen by the consumer",
)

def validate_trajectory(metadata, records):
    """Validate measured frame-to-frame deltas for BOTH arms without online action bounds."""
    if not isinstance(metadata, dict) or metadata.get("format") != TRAJECTORY_FORMAT:
        raise ReferenceError("unsupported trajectory reference format")
    expected_pose = dict(
        reference={"left": "left_ee", "right": "right_ee"},
        coordinate_frame="environment",
        position_unit="metre",
        quaternion_order="wxyz",
    )
    pose = metadata.get("pose")
    if not isinstance(pose, dict) or any(pose.get(k) != v for k, v in expected_pose.items()):
        raise ReferenceError("unsupported trajectory pose semantics")
    action = metadata.get("action")
    if not isinstance(action, dict) or any(action.get(k) != v for k, v in ACTION_SEMANTICS.items()):
        raise ReferenceError("unsupported trajectory action semantics")
    count = validate_sequence(metadata, records)
    unknown = {"left": [], "right": []}
    for index, record in enumerate(records):
        validate_frame(record, index)
        action = record["action"]
        if index == count - 1:
            if action is not None:
                raise ReferenceError("last trajectory action must be null")
            continue
        if not isinstance(action, dict) or set(action) != {"left", "right"}:
            raise ReferenceError("trajectory action requires both arms")
        for arm in ("left", "right"):
            part = action[arm]
            if not isinstance(part, dict) or set(part) != {"dpos", "dquat", "gripper"}:
                raise ReferenceError("invalid trajectory arm action")
            validate_delta(part)
            if part["gripper"] is None:
                unknown[arm].append(index)
            elif not finite_number(part["gripper"]) or not 0 <= part["gripper"] <= 1:
                raise ReferenceError("invalid trajectory gripper")
    sampling = metadata.get("sampling")
    if not isinstance(sampling, dict):
        raise ReferenceError("missing trajectory sampling metadata")
    dt = sampling.get("nominal_sample_interval_seconds")
    if (dt is None and count != 1) or (dt is not None and (not finite_number(dt) or dt <= 0)):
        raise ReferenceError("invalid trajectory sample interval")
    if dt is not None and not math.isclose(dt * metadata["fps"], 1.0, rel_tol=1e-6):
        raise ReferenceError("trajectory fps and nominal sample interval disagree")
    supplied_unknown = sampling.get("unknown_gripper_action_frames")
    if (
        not isinstance(supplied_unknown, dict)
        or set(supplied_unknown) != {"left", "right"}
        or any(
            not isinstance(supplied_unknown[a], list) or any(type(i) is not int for i in supplied_unknown[a])
            for a in unknown
        )
        or supplied_unknown != unknown
    ):
        raise ReferenceError("unknown gripper frames disagree with trajectory")
    gaps = sampling.get("sampling_gaps")
    if not isinstance(gaps, list):
        raise ReferenceError("invalid trajectory sampling gaps")
    previous = -1
    for gap in gaps:
        if not isinstance(gap, dict) or set(gap) != {"from_frame", "to_frame", "interval_seconds"}:
            raise ReferenceError("invalid trajectory sampling gap")
        start, end, interval = gap["from_frame"], gap["to_frame"], gap["interval_seconds"]
        if (
            type(start) is not int
            or type(end) is not int
            or not previous < start < count - 1
            or end != start + 1
            or not finite_number(interval)
            or interval <= dt
            or any(start not in unknown[a] for a in unknown)
        ):
            raise ReferenceError("sampling gaps require unknown commands for both arms")
        previous = start
