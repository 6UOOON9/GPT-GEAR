"""Owner-thread GR1 adapter; robot proprioception, head RGB and optional measured depth."""
from __future__ import annotations
import threading
import time
import numpy as np
from scipy.spatial.transform import Rotation
from control import delta
from environments.robocasa_gr1.environment import ARMS, CAMERAS, CONTROL_FREQ, HAND_NAMES, HAND_LOW, HAND_HIGH, make_environment
from control.profiles import control_profile


def pose_of(position, matrix):
    q = Rotation.from_matrix(np.asarray(matrix).reshape(3, 3)).as_quat()
    return np.r_[position, q[[3, 0, 1, 2]]].tolist()


def measured_state(env, hand_commands=None):
    robot, sim = env.robots[0], env.sim
    arms = {}
    for arm in ARMS:
        grip = robot.gripper[arm]
        site = robot.eef_site_id[arm]
        names = robot.part_controllers[arm].joint_names
        joints = [sim.model.joint_name2id(n) for n in names]
        actuators = [sim.model.actuator_name2id(n) for n in grip.actuators]
        hand_joints = sim.model.actuator_trnid[actuators, 0]
        hq = sim.data.qpos[sim.model.jnt_qposadr[hand_joints]]
        arms[arm] = dict(
            ee_pose=pose_of(sim.data.site_xpos[site], sim.data.site_xmat[site]),
            ee_reference=grip.important_sites['grip_site'],
            joint_names=list(names), joint_positions=sim.data.qpos[sim.model.jnt_qposadr[joints]].tolist(),
            joint_velocities=sim.data.qvel[sim.model.jnt_dofadr[joints]].tolist(),
            hand_joint_names=[sim.model.joint_id2name(int(j)) for j in hand_joints],
            hand_joint_positions=hq.tolist(), hand_positions=hq[[1, 3, 5, 7, 9, 10]].tolist(),
            hand_command=None if hand_commands is None else list(hand_commands[arm]),
            hand_control_names=list(HAND_NAMES), hand_command_unit='radian_position_target',
            hand_command_limits=[list(HAND_LOW), list(HAND_HIGH)],
            hand_actuator_limits=sim.model.actuator_ctrlrange[actuators].tolist())
    head = sim.model.body_name2id('robot0_head_pitch')
    torso = [sim.model.joint_name2id(n) for n in robot.part_controllers['torso'].joint_names]
    return dict(arms=arms, coordinate_frame='environment', position_unit='m',
                head_pose=pose_of(sim.data.body_xpos[head], sim.data.body_xmat[head]),
                torso_joint_positions=sim.data.qpos[sim.model.jnt_qposadr[torso]].tolist())


def native_action(env, poses, hands):
    """World absolute grip-site poses -> the recorded absolute/base IK action."""
    robot, sim = env.robots[0], env.sim
    cc = robot.composite_controller
    splits = cc._whole_body_controller_action_split_indexes
    base = sim.model.body_name2id('robot0_base')
    rb = np.asarray(sim.data.body_xmat[base]).reshape(3, 3)
    pb = np.asarray(sim.data.body_xpos[base])
    action = np.zeros(len(cc.action_limits[0]))
    for arm in ARMS:
        pose = np.asarray(poses[arm], dtype=float)
        r = Rotation.from_quat(pose[[4, 5, 6, 3]]).as_matrix()
        site = robot.gripper[arm].important_sites['grip_site']
        start, end = splits[site if site in splits else arm]
        action[start:end] = np.r_[rb.T @ (pose[:3] - pb), Rotation.from_matrix(rb.T @ r).as_rotvec()]
        start, end = splits[arm + '_gripper']
        action[start:end] = hands[arm]
    return action


class RobocasaNative:
    def __init__(self, args):
        self.benchmark = 'robocasa-gr1'
        self.control_profile = control_profile(self.benchmark)
        self.owner = threading.get_ident()
        self.args, self.video, self.env = args, None, None
        self.measured_depth = args.measured_depth
        self.depth_m = None
        self.action_count = self.initialization_steps = 0
        self.success = self.terminal = self.uncertain = self.closed = False
        name = args.task
        self.identity = dict(task=name, seed=args.seed, measured_depth=args.measured_depth)
        try:
            self.env = make_environment(name, seed=args.seed, image_size=args.image_size,
                                        horizon=args.max_native_steps, data_root=args.data_root)
            self.env.reset()
            state = measured_state(self.env)
            self.targets = {arm: np.asarray(state['arms'][arm]['ee_pose']) for arm in ARMS}
            self.hands = {arm: state['arms'][arm]['hand_positions'] for arm in ARMS}
            self.instruction = self.env.get_ep_meta()['lang']
            self.success = bool(self.env._check_success())
            self.terminal = self.success
            if self.success:
                raise ValueError('initial state already satisfies task')
            self._capture()
            if args.save_video:
                from execution.video import EpisodeVideo
                self.video = EpisodeVideo(args.output, args.image_size, CONTROL_FREQ, CAMERAS)
                self._record_frame()
            hold = {arm: state['arms'][arm]['ee_pose'] for arm in ARMS}
            for _ in range(min(10, args.max_native_steps)):
                if self.terminal: break
                self._step(native_action(self.env, hold, self.hands), initialization=True)
            self._camera_metadata = self._calibrate()
        except BaseException:
            self.close()
            raise

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError('native simulator access requires owner thread')

    def _capture(self):
        rendered = self.env.sim.render(height=self.args.image_size, width=self.args.image_size,
                                       camera_name='egoview', depth=self.measured_depth)
        if self.measured_depth:
            from robosuite.utils.camera_utils import get_real_depth_map
            rgb, buffer = rendered
            self.depth_m = np.ascontiguousarray(get_real_depth_map(self.env.sim, buffer)[::-1], dtype=np.float32)
            if (self.depth_m.shape != (self.args.image_size, self.args.image_size)
                    or not np.isfinite(self.depth_m).all() or np.any(self.depth_m <= 0)):
                raise ValueError('invalid metric depth observation')
        else:
            rgb = rendered
        self.rgb = np.ascontiguousarray(rgb[::-1])
        if self.rgb.dtype != np.uint8 or self.rgb.shape != (self.args.image_size, self.args.image_size, 3):
            raise ValueError('invalid RGB observation')

    def _record_frame(self):
        if self.video is not None: self.video.append([self.rgb])

    def _step(self, action, *, initialization=False):
        self._owner()
        if self.terminal: raise RuntimeError('episode terminal')
        try:
            self.env.step(action)
            self.action_count += 1
            self.initialization_steps += int(initialization)
            self._capture()
            self._record_frame()
            self.success = bool(self.env._check_success())
            self.terminal = self.success or self.action_count >= self.args.max_native_steps
        except BaseException:
            self.uncertain = self.terminal = True
            raise

    def robot_state(self):
        self._owner()
        raw = measured_state(self.env, self.hands)
        state = {f'{arm}_{key}': value for arm in ARMS for key, value in raw['arms'][arm].items()}
        state.update(head_pose=raw['head_pose'], torso_joint_positions=raw['torso_joint_positions'])
        if any(not np.isfinite(state[f'{arm}_ee_pose']).all() for arm in ARMS):
            raise ValueError('nonfinite GR1 pose')
        return state

    def _calibrate(self):
        sim = self.env.sim
        cid = sim.model.camera_name2id('egoview')
        h, w = self.rgb.shape[:2]
        f = .5 * h / np.tan(float(sim.model.cam_fovy[cid]) * np.pi / 360.)
        camera = np.eye(4)
        camera[:3, :3] = np.asarray(sim.data.cam_xmat[cid]).reshape(3, 3)
        camera[:3, 3] = sim.data.cam_xpos[cid]
        return dict(intrinsic_K=[[f, 0., w/2], [0., f, h/2], [0., 0., 1.]],
                    camera_to_env_gl=camera.tolist(), calibration_reference='head',
                    calibration_mount_signature=f'gr1:egoview:{sim.model.cam_bodyid[cid]}')

    def observe(self):
        self._owner()
        view = dict(self._camera_metadata, rgb=self.rgb)
        if self.measured_depth:
            view['depth_m'] = self.depth_m
        return dict(instruction=self.instruction, robot_state=self.robot_state(),
                    views={'egoview': view}, captured_at=time.time())

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
        if self.terminal:
            raise ValueError('episode terminal')
        if (not isinstance(commands, list) or not commands or
                len({c.get('arm') for c in commands}) != len(commands)):
            raise ValueError('expected distinct GR1 arm commands')
        state = self.robot_state()
        targets = {arm: pose.copy() for arm, pose in self.targets.items()}
        hands = {arm: list(values) for arm, values in self.hands.items()}
        for part in commands:
            arm = part.get('arm')
            if arm not in ARMS or part.get('type') != 'delta_pose' or part.get('frame') != 'environment':
                raise ValueError('unsupported GR1 native command')
            pose = np.asarray(state[f'{arm}_ee_pose'])
            # The servo bounds reference advancement, not its distance from a lagging robot.
            dp = np.asarray(part['dpos'], dtype=float)
            dq = delta.normalize_quat(np.asarray(part['dquat'], dtype=float))
            if dp.shape != (3,) or not np.isfinite(dp).all():
                raise ValueError('invalid reference increment')
            targets[arm] = np.r_[pose[:3] + dp, delta.multiply(dq, pose[3:])]
            if 'hand' in part:
                if len(part['hand']) != 6:
                    raise ValueError('hand requires six targets')
                hands[arm] = [delta.scalar(v, 'hand', -3., 3.) for v in part['hand']]
        action = native_action(self.env, targets, hands)
        self.targets, self.hands = targets, hands
        self._step(action)
        return dict(success=True)

    def ended(self): return self.status()['terminal']

    def finalize(self):
        self._owner()
        self.terminal = True
        return dict(video=self.video.finish() if self.video is not None else dict(enabled=False, complete=False))

    def close(self):
        self._owner()
        if not self.closed:
            self.closed = True
            try:
                if self.video is not None: self.video.finish()
            finally:
                if self.env is not None: self.env.close()

    def control_metadata(self):
        return dict(budget_unit='env_step', control_freq_hz=CONTROL_FREQ,
                    step_limit=self.args.max_native_steps, initialization_steps=self.initialization_steps,
                    hand_names=list(HAND_NAMES), target_mode='reference_trajectory')

    def result(self, unused=None):
        from execution.native_result import result
        official = dict(check_success=bool(self.env._check_success()), reward_source='env._check_success')
        return result(self, official)
