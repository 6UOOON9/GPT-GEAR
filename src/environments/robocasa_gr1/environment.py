"""Pinned GR1 tabletop task registry and simulator construction."""
from copy import deepcopy
import json
from pathlib import Path

CAMERAS = ('egoview',)
ARMS = ('right', 'left')
CONTROL_FREQ = 20
HAND_NAMES = ('pinky_flexion', 'ring_flexion', 'middle_flexion', 'index_flexion',
              'thumb_flexion', 'thumb_rotation')
# Preserve raw demonstration targets; native actuators apply physical limits.
HAND_LOW = (-3.,) * 6
HAND_HIGH = (3.,) * 6


def environment_metadata(name, data_root):
    import h5py
    try:
        with h5py.File(Path(data_root) / f'{name}.hdf5', 'r') as f:
            return json.loads(f['data'].attrs['env_args'])
    except (KeyError, TypeError) as exc:
        raise ValueError('GR1 HDF5 requires data.attrs[env_args] JSON') from exc


def make_environment(name, *, data_root, seed=0, image_size=256, horizon=1000):
    import robocasa  # noqa: F401
    import robosuite
    import numpy as np
    import random
    meta = environment_metadata(name, data_root)
    kwargs = deepcopy(meta['env_kwargs'])
    kwargs.pop('env_lang', None)
    kwargs.update(env_name=name, seed=seed, has_renderer=False,
                  renderer='mujoco', has_offscreen_renderer=True,
                  use_camera_obs=False, camera_names=list(CAMERAS),
                  camera_heights=image_size, camera_widths=image_size,
                  render_camera='egoview', control_freq=CONTROL_FREQ,
                  ignore_done=True, horizon=horizon)
    validate_controller(kwargs)
    # robosuite's robot initialization noise uses the legacy global RNG,
    # independently of the environment's seeded Generator.
    np.random.seed(seed)
    random.seed(seed)
    return robosuite.make(**kwargs)


def validate_controller(kwargs):
    controller = kwargs.get('controller_configs') if isinstance(kwargs, dict) else None
    if not isinstance(controller, dict) or controller.get('type') != 'WHOLE_BODY_MINK_IK':
        raise ValueError('Expected original demonstration EEF controller')
    specific = controller.get('composite_controller_specific_configs', {})
    if not isinstance(specific, dict):
        raise ValueError('missing native IK configuration')
    if (specific.get('ik_input_type') != 'absolute' or specific.get('ik_input_ref_frame') != 'base'
            or specific.get('ik_input_rotation_repr') != 'axis_angle'
            or specific.get('use_joint_angle_action_input')):
        raise ValueError('Expected absolute/base/axis_angle native EEF inputs')
