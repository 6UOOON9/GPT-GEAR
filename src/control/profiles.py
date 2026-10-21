"""Serializable, simulator-independent control capabilities."""
from copy import deepcopy
from environments.benchmarks import BENCHMARKS


def control_profile(benchmark):
    if benchmark not in BENCHMARKS:
        raise ValueError(f'unknown benchmark: {benchmark}')
    arms = ('left', 'right') if benchmark in ('robodojo', 'robocasa-gr1', 'robotwin') else ('robot0',)
    profile = dict(
        arms={arm: dict(pose_key=f'{arm}_ee_pose',
                        control_point=f'{arm}_ee' if benchmark == 'robodojo' else 'robot0_grip_site',
                        gripper='fraction' if benchmark == 'robodojo' else 'binary') for arm in arms},
        coordinate_frame='environment', position_unit='m', quaternion_order='wxyz',
        max_translation=0.20, max_rotation=1.5707963267948966, max_steps=100,
        translation_step=dict(minimum=0.001, maximum=0.02, default=0.01),
        rotation_step=dict(minimum=0.005, maximum=0.10, default=0.05),
        budget_unit='synchronized_take_action' if benchmark == 'robodojo' else 'env_step',
        cameras=['agentview', 'robot0_eye_in_hand'] if benchmark in ('libero-plus', 'libero-geomotion') else None,
    )
    if benchmark == 'robotwin':
        for arm in arms:
            profile['arms'][arm].update(control_point=f'robotwin_native_{arm}_ee')
        profile.update(cameras=['head_camera', 'left_camera', 'right_camera'],
                       budget_unit='take_action_ee_call')
    elif benchmark == 'robocasa-gr1':
        for arm in arms:
            profile['arms'][arm].update(control_point=f'gripper0_{arm}_grip_site', gripper='hand',
                hand_names=['pinky_flexion', 'ring_flexion', 'middle_flexion', 'index_flexion',
                            'thumb_flexion', 'thumb_rotation'])
        profile.update(cameras=['egoview'], target_mode='reference_trajectory')
    elif benchmark == 'univtac':
        profile['arms']['robot0'].update(
            control_point='gripper_center', gripper='position_m',
            gripper_position_limits_m=[0.0, 0.04])
        profile.update(cameras=['head', 'wrist'], environment_frame='robot_base',
                       budget_unit='control_step', gripper_tolerance_m=0.00005)
    return profile


def validate_profile(profile, benchmark):
    if profile != control_profile(benchmark):
        raise ValueError('incompatible control profile')
    return deepcopy(profile)
