"""UniVTAC RGB/proprioceptive adapter and generic measured-state DLS servo.

Only reset() invokes the benchmark's standard preparation. Model-time motion does
not access actors, task target poses, contact/tactile readings or expert actions.
"""
from __future__ import annotations
import importlib
import json
import random
import threading
import time
import numpy as np
from control import delta
from environments.univtac import gripper as grip
from perception.calibration import ee_transform
from environments.benchmarks import TASKS as ALL_TASKS
from control.profiles import control_profile
from perception.modalities import observation_profile
TASKS = ALL_TASKS['univtac']

CAMERAS = ('head', 'wrist')

class UniVTACNative:
    def __init__(self, args):
        import torch
        self.torch = torch
        self.benchmark = 'univtac'
        self.control_profile = control_profile(self.benchmark)
        self.tactile_mode = args.tactile_mode
        self.observation_profile = observation_profile(self.benchmark, self.tactile_mode)
        self.owner = threading.get_ident()
        self.args = args
        self.video = self.tactile_video = self.sensor_log = self.env = None
        self.action_count = self.physics_steps = self.policy_actions = 0
        self.initialization_steps = 0
        self.success = self.terminal = self.uncertain = self.closed = False
        self.early_stop = False
        self.identity = dict(task=args.task, seed=args.seed, tactile_mode=args.tactile_mode)
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        try:
            module = importlib.import_module('envs.' + args.task)
            cfg = module.TaskCfg()
            cfg.seed = args.seed
            cfg.save_dir = args.output / 'simulation'
            cfg.scene.num_envs = 1
            cfg.sim.device = f'cuda:{args.device_id}'
            cfg.sim.enable_scene_query_support = True
            cfg.decimation = 1
            cfg.video_frequency = cfg.render_frequency = 0
            cfg.save_frequency = 1
            cfg.reset_time_limit = 1200
            cfg.step_lim = args.max_native_steps * args.control_decimation
            cfg.random_texture = False
            cfg.obs_data_type = {'camera': ['rgb'], 'embodiment': ['joint', 'ee']}
            for camera in cfg.cameras:
                camera.width, camera.height = args.image_width, args.image_height
            self.env = module.Task(cfg, mode='eval')
            self.env.reset(seed=args.seed)
            if not self.env.plan_success:
                raise RuntimeError('official task preparation failed')
            self.env.instruction = TASKS[args.task]['instruction']
            self.initialization_steps = int(self.env.step_count)
            self.robot_manager = self.env._robot_manager
            self.robot = self.robot_manager.robot
            self._arm_ids = self.robot_manager._arm_ids
            self._jacobian_id = self.robot_manager._jacobi_body_idx
            self.gripper_target = grip.validate_position(self.robot_manager.get_gripper_qpos())
            limits = self.robot.data.soft_joint_pos_limits[0, self.robot_manager._gripper_ids].detach().cpu().numpy()
            if not (np.all(limits[:, 0] <= grip.MIN_POSITION_M + 1e-7)
                    and np.all(limits[:, 1] >= grip.MAX_POSITION_M - 1e-7)):
                raise RuntimeError(f'Panda finger limits do not support continuous contract: {limits}')
            self.attachment_counts = {name: len(tact.attachment.attachment_points_idx)
                                     for name, tact in self.env._tactile_manager.tactiles.items()}
            if not all(self.attachment_counts.values()): raise RuntimeError('gelpad has no attachment vertices')
            # Refresh all sensors in ALL conditions: some native termination predicates
            # consume tactile height maps. Only public observations are ablated.
            self.env._update_render()
            self.force_reader = None
            if self.observation_profile['contact_forces']:
                from environments.univtac.forces import NativeContactForces
                self.force_reader = NativeContactForces(self.env)
            self._camera_metadata = self._calibrate()
            self.success = bool(self.env.check_success())
            self.terminal = self.success
            if self.success:
                raise ValueError('initial state already satisfies task')
            if args.save_video:
                from execution.video import EpisodeVideo
                self.video = EpisodeVideo(args.output, (args.image_height, args.image_width),
                                          120 / args.control_decimation, CAMERAS, includes_initialization=False)
                if self.observation_profile['tactile_images']:
                    tactile_output = args.output / 'tactile_recording'
                    tactile_output.mkdir(exist_ok=False)
                    shape = self._tactile_rgb('left_tactile').shape[:2]
                    self.tactile_video = EpisodeVideo(tactile_output, shape,
                        120 / args.control_decimation, ('left_tactile', 'right_tactile'), includes_initialization=False)
                if self.force_reader is not None:
                    self.sensor_log = (args.output / 'recorded_contact_forces.jsonl').open('x')
                self._record_frame()
            from execution.artifacts import write_json
            write_json(args.output / 'initialization.json', {
                'seed': args.seed, 'initialization_physics_steps': self.initialization_steps,
                'official_reset_and_pre_move': True, 'expert_play_once_called': False,
                'tactile_mode': args.tactile_mode, 'tactile_policy_input': args.tactile_mode != 'none', 'tactile_contact_physics': True,
                'all_conditions_update_tactile': True, 'contact_force_source': self.force_reader.metadata if self.force_reader else None,
                'attachment_vertices': self.attachment_counts,
                'initial_success': self.success, 'control_reference': 'gripper_center',
                'action_contract': grip.ACTION_CONTRACT, 'gripper_position_limits_m': [grip.MIN_POSITION_M, grip.MAX_POSITION_M],
                'gripper_state_source': 'panda_finger_joint1 measured position; same target sent to both fingers',
                'control_hz': 120 / args.control_decimation,
                'max_native_steps': args.max_native_steps, 'max_policy_actions': args.max_policy_actions,
                'native_control': 'DLS differential IK, bounded joint-position updates (force=True, repository convention)'})
        except BaseException:
            self.close()
            raise

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('simulator access requires its owner thread')

    def _rgb(self, name):
        rgb = self.env._camera_manager.cameras[name].data.output['rgb'][0, ..., :3].detach().cpu().numpy()
        if rgb.dtype != np.uint8 or rgb.shape != (self.args.image_height, self.args.image_width, 3):
            raise ValueError('invalid RGB observation')
        return np.ascontiguousarray(rgb)

    def _record_frame(self):
        if self.video is not None:
            self.video.append([self._rgb(name) for name in CAMERAS])
            if self.tactile_video is not None:
                self.tactile_video.append([self._tactile_rgb(name) for name in ('left_tactile', 'right_tactile')])
            if self.sensor_log is not None:
                self.sensor_log.write(json.dumps(dict(action_count=self.action_count, physics_steps=self.physics_steps,
                    contact_forces=self.force_reader.read()), allow_nan=False) + '\n')
                self.sensor_log.flush()

    def robot_state(self):
        self._owner()
        manager = self.robot_manager
        pose = manager.get_gripper_center_pose().tolist()
        joints = self.robot.data.joint_pos[0].detach().cpu().numpy()
        velocities = self.robot.data.joint_vel[0].detach().cpu().numpy()
        state = dict(ee_pose=pose, ee_reference='gripper_center',
                     coordinate_frame='robot_base', position_unit='m', quaternion_order='wxyz',
                     joint_positions=joints[:7].tolist(), joint_velocities=velocities[:7].tolist(),
                     gripper_position_m=float(joints[int(manager._gripper_ids[0])]),
                     hand_to_gripper_center_m=[0., 0., manager.cfg.gripper_offset])
        if not all(np.isfinite(state[k]).all() for k in ('ee_pose','joint_positions','joint_velocities','gripper_position_m')):
            raise ValueError('nonfinite robot state')
        return state

    def _calibrate(self):
        root_pose = np.r_[self.robot.data.root_link_pos_w[0].cpu().numpy(),
                          self.robot.data.root_link_quat_w[0].cpu().numpy()]
        world_to_base = np.linalg.inv(ee_transform(root_pose))
        result = {}
        for name in CAMERAS:
            camera = self.env._camera_manager.cameras[name]
            camera._update_poses(camera._ALL_INDICES)
            pose = np.r_[camera.data.pos_w[0].cpu().numpy(), camera.data.quat_w_opengl[0].cpu().numpy()]
            result[name] = dict(intrinsic_K=camera.data.intrinsic_matrices[0].cpu().numpy().tolist(),
                camera_to_env_gl=(world_to_base @ ee_transform(pose)).tolist(),
                calibration_reference='environment' if name == 'head' else 'robot0_ee',
                calibration_mount_signature=f'univtac:gsmini:{name}:{self.args.image_width}x{self.args.image_height}')
        return result

    def _tactile_rgb(self, name):
        value = self.env._tactile_manager.tactiles[name].sensor.data.output['tactile_rgb'][0]
        rgb = value.detach().cpu().numpy()
        if not np.isfinite(rgb).all() or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError('invalid native tactile RGB')
        # Native optical output is normally uint8; preserve its fixed 0..255 scale.
        if rgb.dtype != np.uint8:
            if rgb.min() < 0 or rgb.max() > 255:
                raise ValueError('unexpected tactile image range')
            rgb = np.rint(rgb).astype(np.uint8)
        return np.ascontiguousarray(rgb)

    def observe(self):
        self._owner()
        observation = dict(instruction=self.env.instruction,
            robot_state={f'robot0_{k}': v for k, v in self.robot_state().items()}, captured_at=time.time(),
            views={name: dict(self._camera_metadata[name], rgb=self._rgb(name)) for name in CAMERAS})
        if self.observation_profile['tactile_images']:
            observation['tactile_images'] = {name: self._tactile_rgb(name)
                for name in self.observation_profile['tactile_images']}
        if self.observation_profile['contact_forces']:
            observation['contact_forces'] = self.force_reader.read()
        return observation

    def status(self):
        self._owner()
        return dict(terminal=self.terminal, success=self.success, action_count=self.action_count,
                    decision_steps=self.action_count, initialization_steps=self.initialization_steps,
                    physics_steps=self.physics_steps, control_hz=120/self.args.control_decimation,
                    step_limit=self.args.max_native_steps,
                    remaining_steps=max(0, self.args.max_native_steps-self.action_count),
                    policy_actions=self.policy_actions, policy_action_limit=self.args.max_policy_actions,
                    task_early_stop=self.early_stop, outcome_unknown=self.uncertain, **self.identity)

    def _joint_target(self, goal_p, goal_q):
        """DLS at the gripper center, using only robot kinematics and measured joints."""
        torch = self.torch
        state = np.asarray(self.robot_manager.get_gripper_center_pose().tolist())
        rotation = ee_transform(state)[:3, :3]
        dp = delta.limit_norm(goal_p-state[:3], 0.0015)
        dr = delta.limit_norm(delta.rotation_error(goal_q, state[3:]), 0.015)
        jacobian = self.robot.root_physx_view.get_jacobians()[0, self._jacobian_id, :, self._arm_ids].cpu().numpy()
        root_quat = self.robot.data.root_link_quat_w[0].cpu().numpy()
        root_R = ee_transform(np.r_[np.zeros(3), root_quat])[:3, :3]
        jacobian[:3] = root_R.T @ jacobian[:3]
        jacobian[3:] = root_R.T @ jacobian[3:]
        offset = rotation @ np.array([0., 0., self.robot_manager.cfg.gripper_offset])
        x,y,z = offset
        skew = np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
        jacobian[:3] -= skew @ jacobian[3:]
        error = np.r_[dp,dr]
        dq = jacobian.T @ np.linalg.solve(jacobian @ jacobian.T + 0.0004*np.eye(6), error)
        dq = np.clip(dq, -0.025, 0.025)
        q = self.robot.data.joint_pos[0, self._arm_ids].cpu().numpy()
        limits = self.robot.data.soft_joint_pos_limits[0, self._arm_ids].cpu().numpy()
        return torch.tensor(np.clip(q+dq, limits[:,0], limits[:,1]), dtype=torch.float32, device=self.env.device)

    def execute(self, commands):
        self._owner()
        if not isinstance(commands, list) or len(commands) != 1 or commands[0].get('arm') != 'robot0':
            raise ValueError('expected exactly one robot0 command')
        command = commands[0]
        if self.terminal: raise ValueError('episode terminal')
        if command.get('type') != 'delta_pose' or command.get('frame') != 'environment':
            raise ValueError('unsupported native command')
        displacement = delta.vector(command['dpos'], 'dpos', delta.MAX_TRANSLATION_STEP)
        rotation = delta.quaternion(command['dquat'], 'dquat', delta.MAX_ROTATION_STEP)
        if 'gripper' in command:
            raise ValueError('binary gripper commands are unsupported; use gripper_position_m')
        self.gripper_target = grip.validate_position(command.get('gripper_position_m'))
        initial = np.asarray(self.robot_manager.get_gripper_center_pose().tolist())
        goal_p = initial[:3] + displacement
        goal_q = delta.multiply(rotation, initial[3:])
        try:
            for _ in range(self.args.control_decimation):
                arm = self._joint_target(goal_p, goal_q)
                finger = self.robot_manager.get_gripper_qpos()
                finger = float(np.clip(self.gripper_target, finger-grip.MAX_PHYSICS_STEP_M, finger+grip.MAX_PHYSICS_STEP_M))
                action = self.torch.cat([arm, self.torch.tensor([finger], dtype=arm.dtype, device=arm.device)])
                before = self.env.step_count
                self.env.take_action(action, action_type='qpos', force=True)
                if self.env.step_count != before+1: raise RuntimeError('physics step did not advance')
                self.physics_steps += 1
                self.success = bool(self.env.eval_success)
                self.early_stop = bool(self.env.check_early_stop()) if not self.success else False
                if self.success or self.early_stop: break
            self.action_count += 1
            self.terminal = self.success or self.early_stop or self.action_count >= self.args.max_native_steps
            self._record_frame()
        except BaseException:
            self.uncertain = self.terminal = True
            raise
        return dict(success=True)

    def ended(self):
        return self.status()['terminal']

    def after_policy_action(self):
        """Count one completed servo call, independently of native control steps."""
        self._owner()
        self.policy_actions += 1
        if self.policy_actions >= self.args.max_policy_actions and not self.terminal:
            self.finalize()
            return 'policy_action_budget_exhausted'
        return None

    def finalize(self):
        self._owner()
        self.terminal = True
        return dict(video=self.video.finish() if self.video is not None else dict(enabled=False, complete=False),
                    tactile_video=self.tactile_video.finish() if self.tactile_video is not None else dict(enabled=False,complete=False))

    def close(self):
        self._owner()
        if not self.closed:
            self.closed = True
            try:
                if self.video is not None: self.video.finish()
                if self.tactile_video is not None: self.tactile_video.finish()
                if self.sensor_log is not None: self.sensor_log.close()
            finally:
                if self.env is not None: self.env.close()

    def control_metadata(self):
        return dict(budget_unit='control_step', control_freq_hz=120 / self.args.control_decimation,
                    step_limit=self.args.max_native_steps, policy_action_limit=self.args.max_policy_actions,
                    control_decimation=self.args.control_decimation, environment_frame='robot_base',
                    control_point='gripper_center', gripper_position_limits_m=[0., .04],
                    observation_profile=self.observation_profile,
                    contact_force_source=self.force_reader.metadata if self.force_reader else None)

    def result(self, unused=None):
        from execution.native_result import result
        official = dict(check_success=bool(self.env.eval_success), reward_source='env.eval_success',
                        task_early_stop=self.early_stop)
        return result(self, official)
