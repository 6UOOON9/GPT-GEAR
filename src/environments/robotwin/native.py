"""Owner-thread RoboTwin adapter, adapted from the supplied evaluation archive.

Source attribution: NOTICE. No expert rollout.
"""
from functools import partial
import importlib
import json
import random
import threading
import time

import numpy as np
from PIL import Image

from control import delta
from control.profiles import control_profile
from perception.calibration import intrinsic_matrix, rigid_matrix, numeric_array
from .backend import CONFIGS
from .configuration import load_configuration

CAMERAS = ('head_camera', 'left_camera', 'right_camera')


def instruction_for(task, name, REPO):
    description = json.loads((REPO / 'description/task_instruction' / (name + '.json')).read_text())
    text = description['full_description'].replace('<', '').replace('>', '').replace('!!!', '')
    if name == 'adjust_bottle':
        text += ' Required arm: ' + ('left' if task.qpose_tag == 0 else 'right') + '.'
    fields = {'selected_modelname_A': 'Object A', 'selected_modelname_B': 'Object B',
              'selected_modelname': 'Target object', 'object_name': 'Target object',
              'actor_name': 'Container', 'color_name': 'Target mat color'}
    for attribute, label in fields.items():
        value = getattr(task, attribute, None)
        if isinstance(value, str):
            if value.split('_', 1)[0].isdigit():
                value = value.split('_', 1)[1]
            text += f' {label}: {value.replace("_", " ") }.'
    required_arm = getattr(task, 'arm_tag', None)
    if required_arm is not None and str(required_arm) in ('left', 'right'):
        text += f' Designated object-manipulation arm: {required_arm}.'
    return text


def initialize_success_metadata(task, name):
    if name not in ('open_laptop', 'place_object_scale', 'put_object_cabinet'):
        return
    from envs.utils import ArmTag, get_face_prod

    if name == 'open_laptop':
        face_prod = get_face_prod(task.laptop.get_pose().q, [1, 0, 0], [1, 0, 0])
        task.arm_tag = ArmTag('left' if face_prod > 0 else 'right')
    else:
        pose = task.object.get_pose().p
        task.arm_tag = ArmTag('right' if pose[0] > 0 else 'left')
        if name == 'put_object_cabinet':
            task.origin_z = pose[2]


class RoboTwinNative:
    def __init__(self, args):
        self.benchmark = 'robotwin'
        self.control_profile = control_profile(self.benchmark)
        self.owner = threading.get_ident()
        self.args = args
        self.identity = dict(task=args.task, seed=args.seed, task_config=args.task_config)
        self.action_count = self.initialization_steps = 0
        self.success = self.terminal = self.uncertain = self.closed = False
        self.grippers = dict(left='open', right='open')
        self.task = self.video = None
        self.planning = {}
        self._original_planners = {}
        self._camera_metadata = None
        try:
            config, _ = load_configuration(args.env_root, args.task, args.task_config)
            private = args.output / 'private'
            private.mkdir(parents=True, exist_ok=True)
            config.update(task_name=args.task, task_config=CONFIGS[args.task_config],
                seed=args.seed, now_ep_num=0, dual_arm_embodied=True, eval_mode=True,
                render_freq=0, save_data=False, save_path=str(private), eval_video_save_dir=None)
            config['data_type'].update(rgb=True, endpose=True, qpos=True, depth=False,
                pointcloud=False, actor_segmentation=False, mesh_segmentation=False)
            from execution.artifacts import write_json
            write_json(private / 'simulator_config.json', config)
            random.seed(args.seed)
            np.random.seed(args.seed)
            self.task = getattr(importlib.import_module('envs.' + args.task), args.task)()
            # Preserve the supplied integration's instance-local clutter bounds.
            self.task.get_cluttered_table = partial(self.task.get_cluttered_table,
                xlim=[-0.59, 0.59], ylim=[-0.34, 0.34], zlim=[0.741])
            self.task.setup_demo(is_test=True, **config)
            initialize_success_metadata(self.task, args.task)
            self.task.step_lim = args.max_native_steps
            if self.task.take_action_cnt != 0:
                raise ValueError('RoboTwin policy action budget must start at zero')
            self.instruction = instruction_for(self.task, args.task, args.env_root)
            self.task.set_instruction(self.instruction)
            self.success = self._official_success()
            if self.success:
                raise ValueError('initial state already satisfies task; no policy episode available')
            for side in ('left', 'right'):
                original = getattr(self.task.robot, side + '_plan_path')
                self._original_planners[side] = original

                def track(*values, _original=original, _side=side, **keywords):
                    result = _original(*values, **keywords)
                    self.planning[_side] = result.get('status')
                    return result

                setattr(self.task.robot, side + '_plan_path', track)
            self._capture()
            if args.save_video:
                from .recorder import PhysicsVideo
                self.video = PhysicsVideo(self.task, args.output, args.image_size)
        except BaseException:
            self.close()
            raise

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('RoboTwin must run on its owner thread')

    def _official_success(self):
        return bool(self.task.eval_success or self.task.check_success())

    def _capture(self):
        self.raw = self.task.get_obs()
        views, metadata = {}, {}
        for camera in CAMERAS:
            source = self.raw['observation'][camera]
            rgb = np.asarray(source['rgb'])
            if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 1:
                raise ValueError('invalid RoboTwin RGB observation')
            if self._camera_metadata is None:
                intrinsic = intrinsic_matrix(source['intrinsic_cv']).copy()
                height, width = rgb.shape[:2]
                intrinsic[0] *= self.args.image_size / width
                intrinsic[1] *= self.args.image_size / height
                extrinsic = np.asarray(source['extrinsic_cv'])
                if extrinsic.shape == (3, 4):
                    extrinsic = np.vstack([extrinsic, [0., 0., 0., 1.]])
                camera_world_gl = np.linalg.inv(rigid_matrix(extrinsic)) @ np.diag([1., -1., -1., 1.])
                reference = {'head_camera': 'environment', 'left_camera': 'left_ee',
                             'right_camera': 'right_ee'}[camera]
                metadata[camera] = dict(intrinsic_K=intrinsic.tolist(),
                    camera_to_env_gl=camera_world_gl.tolist(), calibration_reference=reference,
                    calibration_mount_signature='robotwin:' + camera)
            else:
                metadata[camera] = self._camera_metadata[camera]
            views[camera] = dict(metadata[camera], rgb=np.asarray(Image.fromarray(rgb).resize(
                (self.args.image_size, self.args.image_size))))
        self._camera_metadata = metadata
        self.views = views
        self.robot_state()  # Validate measured poses before exposing or controlling them.

    def robot_state(self):
        self._owner()
        state = dict(coordinate_frame='environment', quaternion_order='wxyz',
            pose_reference='robotwin_native_ee', gripper_commands=dict(self.grippers))
        for side in ('left', 'right'):
            pose = numeric_array(self.raw['endpose'][side + '_endpose'], (7,))
            if not np.isclose(np.linalg.norm(pose[3:]), 1., atol=1e-4):
                raise ValueError('invalid measured EE quaternion')
            state[side + '_ee_pose'] = pose.tolist()
            state[side + '_gripper'] = delta.scalar(self.raw['endpose'][side + '_gripper'],
                                                     'measured gripper opening', 0., 1.)
        return state

    def observe(self):
        self._owner()
        return dict(instruction=self.instruction, robot_state=self.robot_state(),
                    views=self.views, captured_at=time.time())

    def status(self):
        self._owner()
        return dict(terminal=self.terminal, success=self.success, action_count=self.action_count,
            initialization_steps=0, decision_steps=self.action_count, step_limit=self.args.max_native_steps,
            remaining_steps=max(0, self.args.max_native_steps - self.action_count),
            outcome_unknown=self.uncertain, budget_unit='take_action_ee_call', **self.identity)

    def execute(self, commands):
        self._owner()
        if self.terminal or self.action_count >= self.args.max_native_steps:
            raise ValueError('RoboTwin episode terminal')
        if not isinstance(commands, list) or not 1 <= len(commands) <= 2:
            raise ValueError('expected one or two native arm commands')
        controls = {}
        for command in commands:
            if (not isinstance(command, dict) or command.get('type') != 'delta_pose'
                    or command.get('frame') != 'environment' or command.get('arm') not in ('left', 'right')
                    or command['arm'] in controls):
                raise ValueError('invalid native arm command')
            arm = command['arm']
            gripper = command.get('gripper')
            if gripper is not None and gripper not in ('open', 'close'):
                raise ValueError('gripper must be open, close or null')
            controls[arm] = dict(dpos=delta.vector(command['dpos'], 'dpos', delta.MAX_TRANSLATION),
                dquat=delta.quaternion(command['dquat'], 'dquat', delta.MAX_ROTATION), gripper=gripper)
        vector, grippers = [], dict(self.grippers)
        state = self.robot_state()
        for side in ('left', 'right'):
            pose = np.asarray(state[side + '_ee_pose'])
            if side in controls:
                control = controls[side]
                pose = np.r_[pose[:3] + control['dpos'], delta.multiply(control['dquat'], pose[3:])]
                if control['gripper'] is not None:
                    grippers[side] = control['gripper']
            vector.extend(pose.tolist() + [1. if grippers[side] == 'open' else 0.])
        try:
            before = self.task.take_action_cnt
            if before != self.action_count:
                raise RuntimeError('native command count mismatch before action')
            if self.video is not None:
                self.video.call_index = self.action_count
            self.planning.clear()
            self.grippers = grippers
            self.task.take_action(vector, action_type='ee')
            if self.task.take_action_cnt != before + 1:
                raise RuntimeError('native command count mismatch after action')
            self.action_count += 1
            self.success = self._official_success()
            self.terminal = self.success or self.action_count >= self.args.max_native_steps
            self._capture()
        except BaseException:
            self.uncertain = self.terminal = True
            raise
        failed = [side for side in controls if self.planning.get(side) != 'Success']
        return dict(success=not failed, failed_arm=failed[0] if failed else None,
                    error='native_planning_failed:' + ','.join(failed) if failed else None)

    def ended(self):
        return self.status()['terminal']

    def control_metadata(self):
        return dict(budget_unit='take_action_ee_call', step_limit=self.args.max_native_steps,
            initialization_steps=0, physics_steps_are_separate=True, expert_screening=False,
            task_config=self.args.task_config)

    def finalize(self):
        self._owner()
        self.terminal = True
        return dict(video=self.video.finish() if self.video is not None else dict(enabled=False, complete=False))

    def result(self, unused=None):
        self._owner()
        from execution.native_result import result
        check = bool(self.task.check_success())
        latched = bool(self.task.eval_success)
        official = dict(check_success=check or latched, current_check_success=check, eval_success=latched,
                        success_source='eval_success or check_success()', expert_screening=False)
        value = result(self, official)
        value.update(expert_screening=False, budget_unit='take_action_ee_call',
                     physics_steps=self.video.physics_steps, task_config=self.args.task_config)
        return value

    def close(self):
        self._owner()
        if self.closed:
            return
        self.closed = True
        try:
            self.finalize()
        finally:
            if self.task is not None:
                for side, original in self._original_planners.items():
                    setattr(self.task.robot, side + '_plan_path', original)
                self.task.close_env(clear_cache=True)

