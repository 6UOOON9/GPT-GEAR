# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Native execution adapted from RoboDojo rpent_adapter; independent implementation.
"""Native delta execution and robot-only observation capture (main thread only)."""
from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np

from control import delta


def environment_delta_target(pose, dpos, dquat):
    """Compose a single increment at the measured EE link; never use EEF axes."""
    pose = np.asarray(pose, dtype=float)
    if pose.shape != (7,) or not np.isfinite(pose).all():
        raise ValueError("invalid measured EE pose")
    q = delta.normalize_quat(pose[3:])
    dq = delta.quaternion(dquat, "dquat", delta.MAX_ROTATION_STEP)
    # dq * q: environment-frame rotation (left multiplication), wxyz.
    return np.r_[pose[:3] + dpos, delta.multiply(dq, q)]


def array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def configure_observations(config):
    """Enable calibrated RGB and proprioception, without depth capture."""
    config.eval_cfg.observation.vision.update(
        depth=False, intrinsic_matrix=True, extrinsic_matrix=True)
    config.eval_cfg.observation.robot.update(joint_states=True, world_ee_state=True)


@lru_cache(maxsize=32)
def fixed_link_connection(urdf_path, first, second):
    """Check only the fixed-joint graph; do not estimate a mount from its name."""
    root = ET.parse(urdf_path).getroot()
    links = {link.attrib['name'] for link in root.findall('link')}
    if first not in links or second not in links:
        return False
    graph = {link: set() for link in links}
    for joint in root.findall('joint'):
        if joint.get('type') == 'fixed':
            parent, child = joint.find('parent').get('link'), joint.find('child').get('link')
            graph[parent].add(child)
            graph[child].add(parent)
    visited, pending = set(), [first]
    while pending:
        link = pending.pop()
        if link == second:
            return True
        if link not in visited:
            visited.add(link)
            pending.extend(graph[link] - visited)
    return False


class NativeEnvironment:
    def __init__(self, env):
        if env.num_envs != 1:
            raise ValueError("Codex control requires num_envs=1")
        from control.profiles import control_profile
        self.benchmark = 'robodojo'
        self.control_profile = control_profile(self.benchmark)
        self.identity = dict(task=env.task_name, seed=int(env.eval_seed), layout_id=int(env.env_seeds[0]))
        self.env = env
        self.robots = {r.arm_name.split("_")[0]: r for r in env.robot_manager.robot_list
                       if r.type == "target"}
        if set(self.robots) != {"left", "right"}:
            raise ValueError("Codex control requires a left/right dual-arm robot")
        self.snapshot = 0
        self._control_targets = None

    def camera_calibration_binding(self, name):
        """Private rigid-mount identity; calibrated control fails closed if unknown."""
        config = getattr(self.env, 'camera_config', {})
        settings = config.get(name, {}).get('camera')
        if settings is None:
            return {'calibration_reference': None}
        mount = settings.get('mount_link')
        reference, ee_link = 'environment', None
        if mount is not None:
            reference = None
            manager = self.env.robot_manager
            index = 0
            # Same robot-root allocation as RobotManager._setup_robot_key().
            for i, robot in enumerate(manager.robot_list):
                if manager.use_scene_cfg[i]:
                    robot_root = f'robot{index}'
                    index += 1
                else:
                    robot_root = f'robot{index - 1}'
                if robot.type != 'target' or not mount.startswith(robot_root + '/'):
                    continue
                link = mount[len(robot_root) + 1:]
                try:
                    rigid = fixed_link_connection(str(Path(robot.urdf_path).resolve()), robot.ee_link_name, link)
                except (OSError, ET.ParseError, KeyError, AttributeError):
                    rigid = False
                if rigid:
                    arm = next((arm for arm, candidate in self.robots.items() if candidate is robot), None)
                    if arm is not None:
                        reference, ee_link = f'{arm}_ee', robot.ee_link_name
                break
        if reference is None:
            return {'calibration_reference': None}
        # Offset edits must invalidate calibration even if the reference stays the
        # same. Never send this config or asset paths to the Planner.
        descriptor = {key: settings.get(key) for key in ('mount_link', 'pos', 'ori', 'type', 'mesh')}
        descriptor.update(reference=reference, ee_link=ee_link)
        signature = hashlib.sha256(json.dumps(
            descriptor, sort_keys=True, default=lambda value: array(value).tolist()).encode()).hexdigest()
        return {'calibration_reference': reference, 'calibration_mount_signature': signature}

    def observe(self):
        obs = self.env.get_obs()
        # BaseEnv exposes origins directly; only the inner simulator has scene.
        origin = array(self.env.env_origins[0]).astype(float)
        views = {}
        for name, camera in obs["vision"].items():
            rgb = array(camera["color"])
            intrinsic = array(camera["intrinsic_matrix"]).astype(float)
            camera_to_env = array(camera["extrinsic_matrix"]).astype(float).copy()
            if camera_to_env.shape != (4, 4) or intrinsic.shape != (3, 3):
                raise ValueError("invalid camera calibration")
            # USD camera coordinates: +X right, +Y up, -Z forward.
            camera_to_env[:3, 3] -= origin
            if rgb.ndim != 3 or rgb.shape[2] != 3:
                raise ValueError("RGB geometry mismatch")
            views[name] = {"rgb": rgb.astype(np.uint8),
                           "intrinsic_K": intrinsic, "camera_to_env_gl": camera_to_env,
                           **self.camera_calibration_binding(name)}
        state = {k: array(v).copy() for k, v in obs["state"].items()
                 if k in {f"{a}_{suffix}" for a in self.robots
                          for suffix in ("arm_joint_state", "ee_joint_state", "ee_pose")}}
        for arm, robot in self.robots.items():
            # Use measured robot state, not action labels from observations.
            state[f"{arm}_arm_joint_state"] = array(
                self.env.robot_manager.get_joint(robot, env_idx_list=[0])[0])
            state[f"{arm}_ee_pose"] = array(
                self.env.robot_manager.get_real_endpose(robot, env_idx_list=[0], is_relative=True)[0])
            key = f"{arm}_ee_joint_state"
            physical = float(array(self.env.robot_manager.get_end_effector_real_val(robot, env_idx_list=[0])[0])[0])
            low, high = robot.gripper_scale
            fraction = (physical - low) / (high - low)
            state[key] = np.array([fraction if robot.gripper_move["sign"] == 1 else 1 - fraction]).clip(0, 1)
        self.snapshot += 1
        return {"snapshot_id": self.snapshot, "captured_at": time.time(),
                "instruction": obs["instruction"], "views": views,
                "robot_state": state, "coordinate_frame": "environment"}

    def control_metadata(self):
        """Record actual host configuration without pretending a native command is one physics tick."""
        from control import delta
        return dict(
            budget_unit='synchronized_take_action', step_limit=int(self.env.step_lim),
            physics_dt_seconds=float(self.env.dt),
            rgb_collect_frequency_hz=float(self.env.obs_manager.collect_freq),
            native_command_duration='control-queue dependent; not one physics tick',
            translation_step_default=0.01, rotation_step_default=0.05,
            max_steps_per_arm=delta.MAX_STEPS, max_translation_m=delta.MAX_TRANSLATION,
            max_rotation_rad=float(delta.MAX_ROTATION),
            position_tolerance_m=delta.POSITION_TOLERANCE,
            rotation_tolerance_rad=delta.ROTATION_TOLERANCE,
            gripper_dwell='min(10, arm.max_steps) when explicitly commanded',
            gripper_target='0=closed, 1=open, null=hold',
        )

    def status(self):
        terminal = bool(self.env.end_flag[0])
        return {"terminal": terminal, "success": terminal and bool(self.env.success[0]),
                "action_count": int(self.env.take_action_cnt[0]), "step_limit": int(self.env.step_lim)}

    def ended(self):
        return self.env.is_episode_end()

    def finalize(self):
        # Mark pending failure to request the native final_check path; the
        # reward checker can still promote this to success. Never fake steps.
        if not self.env.is_episode_end():
            self.env.success[0] = False
            self.env.is_episode_end()

    def validate(self, command):
        if not isinstance(command, dict):
            raise ValueError("action must be an object")
        arm, kind = command.get("arm"), command.get("type")
        if arm not in self.robots or kind not in ("joint", "delta_pose"):
            raise ValueError("unknown arm or action type")
        allowed = {"type", "arm", "gripper"}
        allowed |= {"qpos"} if kind == "joint" else set()
        if kind == "delta_pose":
            allowed |= {"frame", "dpos", "dquat"}
        if set(command) - allowed:
            raise ValueError("unknown action fields")
        if "gripper" in command:
            value = command["gripper"]
            if not np.isscalar(value) or not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("gripper must be finite in [0,1]")
        if kind == "delta_pose":
            if command.get("frame") != "environment":
                raise ValueError("delta_pose requires frame=environment")
            # Preserve the native boundary's tolerance for servo roundoff.
            delta.vector(command.get("dpos"), "dpos", delta.MAX_TRANSLATION_STEP + 1e-12)
            delta.quaternion(command.get("dquat"), "dquat", delta.MAX_ROTATION_STEP)
            if "gripper" in command and (isinstance(command["gripper"], (bool, np.bool_))
                    or not isinstance(command["gripper"], (int, float, np.integer, np.floating))):
                raise ValueError("gripper must be a number in [0,1]")
        if kind == "joint":
            robot = self.robots[arm]
            joints = array(self.env.robot_manager.get_joint(robot, env_idx_list=[0])[0])
            qpos = np.asarray(command.get("qpos"), dtype=float)
            if qpos.shape != joints.shape or not np.isfinite(qpos).all():
                raise ValueError("invalid joint target")
            entity = self.env.robot_manager.robot_key[self.env.robot_manager.robot_list.index(robot)]
            limits = array(entity.data.soft_joint_pos_limits[0])[robot.arm_joint_indices]
            if np.any(qpos < limits[:, 0]) or np.any(qpos > limits[:, 1]):
                raise ValueError("joint target outside robot limits")

    def execute(self, commands):
        if not isinstance(commands, list) or not 1 <= len(commands) <= 2:
            raise ValueError("action must contain one or two arm commands")
        if any(not isinstance(command, dict) for command in commands):
            raise ValueError("each arm command must be an object")
        command_arms = [command.get("arm") for command in commands]
        if len(set(command_arms)) != len(command_arms):
            raise ValueError("arm commands must target distinct arms")
        if any(command.get("type") != "delta_pose" for command in commands):
            raise ValueError("only delta_pose is executable")
        # Validate the complete synchronized step before state reads, IK or motion.
        for command in commands:
            self.validate(command)

        state = self.observe()["robot_state"]
        if self._control_targets is None:
            self._control_targets = {
                key: copy.deepcopy(value) for key, value in state.items() if key.endswith("joint_state")
            }
        actions = copy.deepcopy(self._control_targets)

        # Solve and validate every active arm before committing either arm.
        for command in commands:
            arm = command["arm"]
            moving_delta = np.any(command["dpos"]) or np.any(np.asarray(command["dquat"])[1:])
            if moving_delta:
                target = environment_delta_target(
                    state[f"{arm}_ee_pose"],
                    np.asarray(command["dpos"], dtype=float),
                    np.asarray(command["dquat"], dtype=float),
                )
                ik = self.env.robot_manager.solve_ik(
                    target_pose=target, env_idx=0, robot=self.robots[arm], trans="world"
                )
                if ik["status"] != "Success":
                    return {"success": False, "error": "ik_failed", "failed_arm": arm}
                qpos = array(ik["joint_value"])
                if qpos.shape != state[f"{arm}_arm_joint_state"].shape or not np.isfinite(qpos).all():
                    return {"success": False, "error": "invalid_ik_result", "failed_arm": arm}
                try:
                    self.validate({"type": "joint", "arm": arm, "qpos": qpos})
                except (ValueError, TypeError):
                    return {"success": False, "error": "invalid_ik_result", "failed_arm": arm}
                actions[f"{arm}_arm_joint_state"] = qpos
            if "gripper" in command:
                actions[f"{arm}_ee_joint_state"] = np.array([command["gripper"]])

        self.env.take_action(actions)
        self._control_targets = copy.deepcopy(actions)
        return {"success": True}

    def result(self, eval_result):
        details = eval_result.get('details', {})
        valid = bool(details) and eval_result.get('eval_time') == 1
        return dict(complete=True, valid_for_success_rate=valid,
                    task_success=valid and all(d.get('success') is True for d in details.values()),
                    native_steps=self.status()['action_count'], official_result=eval_result,
                    official_result_path=str(Path(self.env.save_dir).resolve() / '_result.json'),
                    official_save_dir=str(Path(self.env.save_dir).resolve()))

    def close(self):
        self.env.close()
