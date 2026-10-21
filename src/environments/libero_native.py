"""Owner-thread LIBERO adapter. No policy, object-state or task-solving code."""
from __future__ import annotations

import threading
import contextlib
import io
import time
from pathlib import Path

import numpy as np

from control import delta
from control.profiles import control_profile

CAMERAS = ('agentview', 'robot0_eye_in_hand')
CONTROL_FREQ = 20


def task_resources(suite, task_id, init_state_index):
    # Imports happen only after entry has installed this run's local config.
    from libero.libero import benchmark
    registry = benchmark.get_benchmark_dict()
    if suite not in registry:
        raise ValueError(f'unknown suite: {suite}')
    with contextlib.redirect_stdout(io.StringIO()):
        tasks = registry[suite](task_order_index=0)
    if not 0 <= task_id < tasks.get_num_tasks():
        raise ValueError('task-id out of range')
    task = tasks.get_task(task_id)
    states = tasks.get_task_init_states(task_id)
    if not 0 <= init_state_index < len(states):
        raise ValueError('init-state-index out of range')
    bddl = tasks.get_task_bddl_file_path(task_id)
    # View/robot/noise suffixes are interpreted by ControlEnv, not actual files.
    physical = bddl.split('_view_')[0] + '.bddl' if '_view_' in bddl and '_initstate_' in bddl else bddl
    if not Path(physical).is_file():
        raise ValueError('task BDDL file is missing')
    return task, bddl, np.asarray(states[init_state_index], dtype=float)


def osc_action(controller, dpos, dquat, gripper):
    """Invert robosuite's affine action scaling; never silently clip metres."""
    if gripper not in ('open', 'close'):
        raise ValueError('invalid directional gripper command')
    physical = np.r_[dpos, delta.rotation_error(np.asarray(dquat, dtype=float), np.array([1., 0., 0., 0.]))]
    low = np.broadcast_to(np.asarray(controller.output_min, dtype=float), (6,))
    high = np.broadcast_to(np.asarray(controller.output_max, dtype=float), (6,))
    ilow = np.broadcast_to(np.asarray(controller.input_min, dtype=float), (6,))
    ihigh = np.broadcast_to(np.asarray(controller.input_max, dtype=float), (6,))
    if (not all(np.isfinite(v).all() for v in (physical, low, high, ilow, ihigh))
            or np.any(high <= low) or np.any(ihigh <= ilow)
            or np.any(physical < low) or np.any(physical > high)):
        raise ValueError('increment incompatible with OSC scaling')
    normalized = (physical - (low + high) / 2) / ((high - low) / (ihigh - ilow)) + (ilow + ihigh) / 2
    return np.r_[normalized, -1. if gripper == 'open' else 1.]


class LiberoNativeBase:
    warmup_steps = 0
    environment_options = {}

    def reset_environment(self, initial):
        self.obs = self.env.reset()
        self.obs = self.env.set_init_state(initial)

    def __init__(self, args):
        from libero.libero.envs import OffScreenRenderEnv
        from robosuite import macros
        from robosuite.utils import transform_utils as T
        self.benchmark = self.benchmark_name
        self.control_profile = control_profile(self.benchmark)
        self.owner = threading.get_ident()
        self.args = args
        self.video = None
        self.env = None
        self.obs = None
        self.action_count = self.initialization_steps = 0
        self.success = self.terminal = self.uncertain = self.closed = False
        self.gripper = 'open'
        self.T = T
        self.image_convention = macros.IMAGE_CONVENTION
        if self.image_convention not in ('opengl', 'opencv'):
            raise ValueError('unsupported robosuite image convention')
        self.task, bddl, initial = task_resources(args.suite, args.task_id, args.init_state_index)
        self.identity = dict(task=f'{args.suite}/{args.task_id}', suite=args.suite, task_id=args.task_id, task_name=self.task.name,
                             seed=args.seed, init_state_index=args.init_state_index)
        try:
            self.env = OffScreenRenderEnv(
                bddl_file_name=bddl, camera_names=list(CAMERAS),
                camera_heights=args.image_size, camera_widths=args.image_size,
                camera_depths=False, camera_segmentations=None, controller='OSC_POSE',
                horizon=args.max_native_steps, ignore_done=True, control_freq=CONTROL_FREQ,
                **self.environment_options,
            )
            self.env.seed(args.seed)
            self.reset_environment(initial)
            robot = self.env.robots[0]
            if len(self.env.robots) != 1 or robot.controller.name != 'OSC_POSE' or not robot.controller.use_delta:
                raise ValueError('requires one Panda-compatible arm with delta OSC_POSE')
            self.success = bool(self.env.check_success())
            self.terminal = self.success
            # An already-solved reset cannot serve as a closed-loop policy evaluation.
            if self.terminal:
                raise ValueError('initial state already satisfies task; no policy episode available')
            if args.save_video:
                from execution.video import EpisodeVideo
                self.video = EpisodeVideo(args.output, args.image_size, CONTROL_FREQ, CAMERAS)
                self._record_frame()
            if not self.terminal:
                for _ in range(min(self.warmup_steps, args.max_native_steps)):
                    self._step(np.r_[np.zeros(6), -1.], initialization=True)
                    if self.terminal:
                        break
            self._camera_metadata = self._calibrate()
        except BaseException:
            self.close()
            raise

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('native simulator access requires owner thread')

    def _step(self, action, *, initialization=False):
        self._owner()
        if self.terminal:
            raise RuntimeError('episode terminal')
        # An exception may occur after physics has advanced: never retry or claim a known count.
        try:
            self.obs, _, _, _ = self.env.step(action)
            self.action_count += 1
            self.initialization_steps += int(initialization)
            self._record_frame()
            self.success = bool(self.env.check_success())
            self.terminal = self.success or self.action_count >= self.args.max_native_steps
        except BaseException:
            self.uncertain = self.terminal = True
            raise

    def _rgb(self, name):
        rgb = np.asarray(self.obs[name + '_image'])
        if rgb.dtype != np.uint8 or rgb.shape != (self.args.image_size, self.args.image_size, 3):
            raise ValueError('invalid RGB observation')
        # Public images and video share the same top-left origin. No extra render/noise call.
        if self.image_convention == 'opengl':
            rgb = rgb[::-1]
        return np.ascontiguousarray(rgb)

    def _record_frame(self):
        if self.video is not None:
            self.video.append([self._rgb(name) for name in CAMERAS])

    def robot_state(self):
        self._owner()
        robot = self.env.robots[0]
        sim = self.env.sim
        # OSC controls the grip site. LIBERO's eef quaternion observable is a body
        # quaternion, so use the actual controlled site's orientation for BOTH pose components.
        p = np.array(sim.data.site_xpos[robot.eef_site_id], copy=True)
        xyzw = self.T.mat2quat(np.array(sim.data.site_xmat[robot.eef_site_id]).reshape(3, 3))
        pose = np.r_[p, xyzw[[3, 0, 1, 2]]]
        state = dict(ee_pose=pose.tolist(), ee_reference='robot0_grip_site',
                     joint_positions=np.asarray(self.obs['robot0_joint_pos']).tolist(),
                     joint_velocities=np.asarray(self.obs['robot0_joint_vel']).tolist(),
                     gripper_joint_positions=np.asarray(self.obs['robot0_gripper_qpos']).tolist(),
                     gripper_command=self.gripper)
        if not all(np.isfinite(state[k]).all() for k in ('ee_pose', 'joint_positions', 'joint_velocities', 'gripper_joint_positions')):
            raise ValueError('invalid robot state')
        return state

    def _calibrate(self):
        self._owner()
        sim = self.env.sim
        metadata = {}
        for name in CAMERAS:
            cid = sim.model.camera_name2id(name)
            image = np.asarray(self.obs[name + '_image'])
            h, w = image.shape[:2]
            f = .5 * h / np.tan(float(sim.model.cam_fovy[cid]) * np.pi / 360.)
            camera = np.eye(4)
            camera[:3, :3] = np.array(sim.data.cam_xmat[cid]).reshape(3, 3)
            camera[:3, 3] = sim.data.cam_xpos[cid]
            metadata[name] = dict(intrinsic_K=[[f, 0., w / 2.], [0., f, h / 2.], [0., 0., 1.]],
                                  camera_to_env_gl=camera.tolist(),
                                  calibration_reference='environment' if name == 'agentview' else 'robot0_ee',
                                  calibration_mount_signature=f'libero:{name}:{sim.model.cam_bodyid[cid]}')
        return metadata

    def observe(self):
        self._owner()
        views = {}
        for name in CAMERAS:
            views[name] = dict(self._camera_metadata[name], rgb=self._rgb(name))
        return dict(instruction=self.env.language_instruction, robot_state={f'robot0_{k}': v for k, v in self.robot_state().items()},
                    views=views, captured_at=time.time())

    def status(self):
        self._owner()
        return dict(terminal=self.terminal, success=self.success, action_count=self.action_count,
                    initialization_steps=self.initialization_steps,
                    decision_steps=self.action_count-self.initialization_steps,
                    step_limit=self.args.max_native_steps,
                    remaining_steps=max(0, self.args.max_native_steps-self.action_count),
                    outcome_unknown=self.uncertain, **self.identity)

    def execute(self, commands):
        self._owner()
        if not isinstance(commands, list) or len(commands) != 1 or commands[0].get('arm') != 'robot0':
            raise ValueError('expected exactly one robot0 command')
        command = commands[0]
        dpos = delta.vector(command.get('dpos'), 'dpos', 0.02 + 1e-12)
        dquat = delta.quaternion(command.get('dquat'), 'dquat', 0.10 + 1e-12)
        if command.get('type') != 'delta_pose' or command.get('frame') != 'environment':
            raise ValueError('unsupported native command')
        gripper = command.get('gripper', self.gripper)
        if gripper not in ('open', 'close'):
            raise ValueError('invalid gripper command')
        action = osc_action(self.env.robots[0].controller, dpos, dquat, gripper)
        self.gripper = gripper
        self._step(action)
        return dict(success=True)

    def ended(self):
        return self.status()['terminal']

    def finalize(self):
        self._owner()
        # End without extra physics. Task success has already been checked after each step.
        self.terminal = True
        return dict(video=self.video.finish() if self.video is not None else
                    dict(enabled=False, complete=False))

    def close(self):
        self._owner()
        if not self.closed:
            self.closed = True
            try:
                if self.video is not None:
                    self.video.finish()
            finally:
                if self.env is not None:
                    self.env.close()

    def control_metadata(self):
        return dict(budget_unit='env_step', control_freq_hz=CONTROL_FREQ,
                    step_limit=self.args.max_native_steps, initialization_steps=self.initialization_steps,
                    control_point='robot0_grip_site', gripper_target='open/close/null=hold')

    def result(self, unused=None):
        from execution.artifacts import write_json
        official = dict(check_success=bool(self.env.check_success()), reward_source='env.check_success')
        if official['check_success'] != self.success:
            raise RuntimeError('official success changed without stepping')
        video = self.video.finish() if self.video is not None else None
        if not video or not video['complete']:
            raise RuntimeError('episode video incomplete')
        path = Path(self.args.output) / 'official_result.json'
        write_json(path, official)
        return dict(complete=True, valid_for_success_rate=not self.uncertain,
                    task_success=self.success, native_steps=self.action_count,
                    initialization_steps=self.initialization_steps,
                    decision_steps=self.action_count-self.initialization_steps,
                    official_result=official, official_result_path=str(path), video=video)
