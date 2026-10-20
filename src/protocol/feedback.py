"""Shared compact feedback contract and model-facing output boundary."""

from __future__ import annotations

from copy import deepcopy

FEEDBACK_FORMAT_VERSION = "compact-arms-v1"
DEFAULT_TOOL_OUTPUT_TOKEN_LIMIT = 8192
FEEDBACK_FIELDS = (
    "success",
    "completed",
    "task_success",
    "stop_reason",
    "executed_steps",
    "max_steps",
    "final_dist_m",
    "final_rotation_error_rad",
    "interrupted",
    "error",
    "outcome_unknown",
    "remaining_actions",
)


def compact_feedback(value):
    """Keep existing summary values, including nulls; never infer missing fields."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("feedback must be an object or null")
    result = {key: deepcopy(value[key]) for key in FEEDBACK_FIELDS if key in value}
    if "per_arm" in value:
        fields = ("completed", "stop_reason", "executed_steps", "max_steps", "final_dist_m", "final_rotation_error_rad", "final_gripper_error_m")
        result["per_arm"] = {
            arm: {key: deepcopy(value["per_arm"][arm][key]) for key in fields if key in value["per_arm"][arm]}
            for arm in value["per_arm"]
        }
    return result


def model_visible_result(result):
    """Detach a result for MCP delivery without modifying the source record.

    Reapply the feedback allowlist at the delivery boundary so internal fields
    cannot leak into model context. Official results, error flags,
    observation identity/calibration and historical action associations survive.
    """
    projected = dict(result)
    if "feedback" in projected:
        projected["feedback"] = compact_feedback(projected["feedback"])
    observation = projected.get("observation")
    if isinstance(observation, dict):
        projected["observation"] = {key: value for key, value in observation.items() if key != "feedback"}
    preceding = projected.get("preceding_action")
    if isinstance(preceding, dict):
        projected["preceding_action"] = dict(preceding)
        if "feedback" in preceding:
            projected["preceding_action"]["feedback"] = compact_feedback(preceding["feedback"])
    return deepcopy(projected)
