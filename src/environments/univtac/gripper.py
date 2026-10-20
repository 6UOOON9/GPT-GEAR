"""Scalar symmetric Panda finger-position contract; no tactile/actor inputs."""
import math
import numbers

from control.profiles import control_profile

ACTION_CONTRACT = 'continuous-gripper-v1'
# Keep native joint-limit checks aligned with the advertised action bounds.
MIN_POSITION_M, MAX_POSITION_M = control_profile('univtac')['arms']['robot0']['gripper_position_limits_m']
MAX_PHYSICS_STEP_M = 0.0005

def validate_position(value):
    if (isinstance(value, bool) or not isinstance(value, numbers.Real)
            or not math.isfinite(value) or not MIN_POSITION_M <= value <= MAX_POSITION_M):
        raise ValueError(f'gripper_position_m must be a finite scalar in [{MIN_POSITION_M}, {MAX_POSITION_M}] metres')
    return float(value)
