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

# Adapted from RPent primitives.act_delta; no policy/model calls.
import numpy as np

from control import delta
from protocol.feedback import compact_feedback


class ControlCancelled(RuntimeError):
    pass


class DeltaController:
    ARM_FIELDS = frozenset(('dpos', 'dquat', 'gripper', 'max_steps'))

    def __init__(self, client, check_cancelled):
        self.profile = client.native.control_profile
        self.ARMS = tuple(self.profile["arms"])
        self.client = client
        self.check_cancelled = check_cancelled

    @staticmethod
    def _count(value, minimum):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f'step count must be an integer >= {minimum}')

    def _validate_arm_action(self, arm, action):
        if not isinstance(action, dict):
            raise ValueError(f'{arm} action must be an object')
        kind = self.profile['arms'][arm]['gripper']
        fields = set(self.ARM_FIELDS)
        if kind in ('hand', 'position_m'):
            fields.remove('gripper')
            fields.add('hand' if kind == 'hand' else 'gripper_position_m')
        unknown = set(action) - fields
        if unknown:
            raise ValueError(f'{arm} action contains unknown fields: {sorted(unknown)}')
        missing = {'dpos', 'max_steps'} - set(action)
        if missing:
            raise ValueError(f'{arm} action requires dpos and max_steps')
        dpos = delta.vector(action['dpos'], f'{arm}.dpos', delta.MAX_TRANSLATION)
        dquat = delta.quaternion(
            [1., 0., 0., 0.] if action.get('dquat') is None else action['dquat'],
            f'{arm}.dquat', delta.MAX_ROTATION)
        gripper = action.get('gripper')
        if gripper is not None:
            if self.profile['arms'][arm]['gripper'] == 'binary':
                if gripper not in ('open', 'close'):
                    raise ValueError('gripper must be open, close or null')
            else:
                gripper = delta.scalar(gripper, f'{arm}.gripper', 0., 1.)
        max_steps = action['max_steps']
        self._count(max_steps, 1)
        if max_steps > delta.MAX_STEPS:
            raise ValueError(f'{arm}.max_steps must be <= {delta.MAX_STEPS}')
        result = dict(dpos=dpos, dquat=dquat, gripper=gripper, max_steps=max_steps)
        if kind == 'hand' and 'hand' in action:
            hand = action['hand']
            if not isinstance(hand, (list, tuple)) or len(hand) != 6:
                raise ValueError('hand requires six radian targets')
            result['hand'] = [delta.scalar(v, 'hand', -3., 3.) for v in hand]
        if kind == 'position_m':
            result['gripper_position_m'] = delta.scalar(
                action.get('gripper_position_m'), f'{arm}.gripper_position_m',
                *self.profile['arms'][arm]['gripper_position_limits_m'])
        return result

    def validate_action(self, *, arms, translation_step=0.01, rotation_step=0.05):
        """Validate and normalize the complete configured-arm request before motion."""
        translation_step = delta.scalar(
            translation_step, 'translation_step', delta.MIN_TRANSLATION_STEP, delta.MAX_TRANSLATION_STEP)
        rotation_step = delta.scalar(
            rotation_step, 'rotation_step', delta.MIN_ROTATION_STEP, delta.MAX_ROTATION_STEP)
        if not isinstance(arms, dict) or set(arms) != set(self.ARMS):
            raise ValueError('action.arms must contain every configured arm exactly once')
        per_arm = {arm: self._validate_arm_action(arm, arms[arm]) for arm in self.ARMS}
        return per_arm, translation_step, rotation_step

    def act_delta(self, *, arms, translation_step=0.01, rotation_step=0.05):
        """Bounded measured-state servo to anchored environment-frame goals."""

        requests, translation_step, rotation_step = self.validate_action(
            arms=arms, translation_step=translation_step, rotation_step=rotation_step)
        self.check_cancelled()
        if self.client.uncertain:
            raise RuntimeError('previous action outcome unknown; session must stop')
        status = self.client.status()
        state = self.client.observe()['robot_state']
        arms = {}

        for arm in self.ARMS:
            request = requests[arm]
            initial = np.asarray(state[f'{arm}_ee_pose'], dtype=float)
            if initial.shape != (7,) or not np.isfinite(initial).all():
                raise ValueError(f'invalid measured {arm} EE pose')
            goal_p = initial[:3] + request['dpos']
            goal_q = delta.multiply(request['dquat'], delta.normalize_quat(initial[3:]))
            has_motion = bool(np.any(request['dpos']) or np.any(request['dquat'][1:]))
            arms[arm] = dict(
                request=request,
                reference_p=initial[:3].copy(),
                reference_q=delta.normalize_quat(initial[3:]),
                goal_p=goal_p,
                goal_q=goal_q,
                has_motion=has_motion,
                minimum_steps=min(10, request['max_steps']) if request['gripper'] is not None or 'hand' in request else 1,
                executed=0,
                stagnant=0,
                best=None,
                progress_reference=None,
                completed=False,
                stop_reason=None,
            )

        def errors(arm):
            context = arms[arm]
            pose = np.asarray(state[f'{arm}_ee_pose'], dtype=float)
            if pose.shape != (7,) or not np.isfinite(pose).all():
                raise ValueError(f'invalid measured {arm} EE pose')
            dp = context['goal_p'] - pose[:3]
            dr = delta.rotation_error(context['goal_q'], delta.normalize_quat(pose[3:]))
            pe, re = float(np.linalg.norm(dp)), float(np.linalg.norm(dr))
            measured_pose_required = self.profile['arms'][arm]['gripper'] in ('hand', 'position_m')
            reached = ((not context['has_motion'] and not measured_pose_required) or
                       (pe <= delta.POSITION_TOLERANCE and re <= delta.ROTATION_TOLERANCE))
            metric = max(pe / delta.POSITION_TOLERANCE, re / delta.ROTATION_TOLERANCE)
            if 'gripper_position_m' in context['request']:
                measured = delta.scalar(
                    state[f'{arm}_gripper_position_m'], f'{arm}.gripper_position_m',
                    *self.profile['arms'][arm]['gripper_position_limits_m'])
                tolerance = self.profile['gripper_tolerance_m']
                ge = abs(context['request']['gripper_position_m'] - measured)
                context['gripper_error_m'] = ge
                reached = reached and ge <= tolerance
                metric = max(metric, ge / tolerance)
            return dp, dr, pe, re, reached, metric

        current = {}
        for arm in self.ARMS:
            current[arm] = errors(arm)
            arms[arm]['best'] = current[arm][-1]
            arms[arm]['progress_reference'] = current[arm][-1]

        executed = 0
        error = None
        reason = 'max_steps'

        try:
            while True:
                self.check_cancelled()
                # Record each arm's local outcome before applying higher-priority
                # episode-wide stops from the same measured native state.
                for arm in self.ARMS:
                    context = arms[arm]
                    if context['stop_reason'] is not None:
                        continue
                    reached = current[arm][4]
                    context['completed'] = reached and context['executed'] >= context['minimum_steps']
                    if context['completed']:
                        context['stop_reason'] = 'completed'
                    elif context['executed'] >= context['request']['max_steps']:
                        context['stop_reason'] = 'max_steps'
                    elif context['stagnant'] >= 5 and not reached and context['executed'] >= context['minimum_steps']:
                        context['stop_reason'] = 'stalled'

                if status.get('success'):
                    reason = 'native_success'
                    break
                if (status.get('step_limit') is not None
                        and status.get('action_count', 0) >= status['step_limit']):
                    reason = 'budget_exhausted'
                    break
                if status['terminal']:
                    reason = 'episode_terminal'
                    break

                active = [arm for arm in self.ARMS if arms[arm]['stop_reason'] is None]
                if not active:
                    if all(arms[arm]['completed'] for arm in self.ARMS):
                        reason = 'completed'
                    elif any(arms[arm]['stop_reason'] == 'stalled' for arm in self.ARMS):
                        reason = 'stalled'
                    else:
                        reason = 'max_steps'
                    break

                commands = []
                for arm in active:
                    context = arms[arm]
                    dp, dr, _, _, reached, _ = current[arm]
                    # Execute a nonzero request at least once, even if it starts inside tolerance.
                    moving = (context['has_motion'] or self.profile['arms'][arm]['gripper'] == 'position_m') and (not reached or context['executed'] == 0)
                    command = {
                        'type': 'delta_pose',
                        'frame': 'environment',
                        'arm': arm,
                        'dpos': delta.limit_norm(dp, translation_step).tolist() if moving else [0., 0., 0.],
                        'dquat': (delta.exp_quat(delta.limit_norm(dr, rotation_step)).tolist()
                                  if moving else [1., 0., 0., 0.]),
                    }
                    if context['request']['gripper'] is not None:
                        command['gripper'] = context['request']['gripper']
                    if self.profile.get('target_mode') == 'reference_trajectory':
                        context['reference_p'] += delta.limit_norm(context['goal_p'] - context['reference_p'], translation_step)
                        context['reference_q'] = delta.multiply(delta.exp_quat(delta.limit_norm(
                            delta.rotation_error(context['goal_q'], context['reference_q']), rotation_step)), context['reference_q'])
                        pose = np.asarray(state[f'{arm}_ee_pose'], dtype=float)
                        command['dpos'] = (context['reference_p'] - pose[:3]).tolist()
                        command['dquat'] = delta.exp_quat(delta.rotation_error(context['reference_q'], pose[3:])).tolist()
                    for key in ('hand', 'gripper_position_m'):
                        if key in context['request']:
                            command[key] = context['request'][key]
                    commands.append(command)
                outcome = self.client.execute(commands)
                count = outcome['executed_actions']

                status, state = outcome['status'], outcome['robot_state']
                current = {arm: errors(arm) for arm in self.ARMS}

                # Count the acknowledged official delta even if the native result
                # violates the one-step contract; feedback must preserve reality.
                executed += count
                for arm in active:
                    arms[arm]['executed'] += count

                if not outcome['success']:
                    error = outcome.get('error') or 'execution_failed'
                    reason = error
                    break
                if count != 1:
                    error = 'unexpected_executed_actions'
                    reason = error
                    break

                for arm in active:
                    context = arms[arm]
                    _, _, _, _, reached, metric = current[arm]
                    context['best'] = min(context['best'], metric)
                    if reached or context['progress_reference'] - context['best'] >= 0.1:
                        context['stagnant'] = 0
                        context['progress_reference'] = context['best']
                    else:
                        context['stagnant'] += 1
        except Exception as exc:
            # Preserve the acknowledged prefix. The client marks uncertain transport outcomes.
            error = str(exc) or type(exc).__name__
            reason = ('cancelled' if isinstance(exc, ControlCancelled) else
                      'outcome_unknown' if self.client.uncertain else 'runtime_failure')

        completed = all(arms[arm]['completed'] for arm in self.ARMS)
        per_arm = {}
        for arm in self.ARMS:
            context = arms[arm]
            _, _, pe, re, _, _ = current[arm]
            arm_reason = context['stop_reason']
            if arm_reason is None:
                arm_reason = reason
            per_arm[arm] = {
                'completed': context['completed'],
                'stop_reason': arm_reason,
                'executed_steps': context['executed'],
                'max_steps': context['request']['max_steps'],
                'final_dist_m': pe,
                'final_rotation_error_rad': re,
            }

            if 'gripper_error_m' in context:
                per_arm[arm]['final_gripper_error_m'] = context['gripper_error_m']

        return compact_feedback({
            'success': error is None,
            'completed': completed,
            'task_success': status.get('success') is True,
            'stop_reason': reason,
            'error': error,
            'outcome_unknown': self.client.uncertain,
            'remaining_actions': (
                max(0, status['step_limit'] - status.get('action_count', 0))
                if status.get('step_limit') is not None and not self.client.uncertain else None),
            'interrupted': reason == 'cancelled',
            'executed_steps': executed,
            'per_arm': per_arm,
        })
