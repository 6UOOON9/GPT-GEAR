"""Compose prompt assets owned by the selected environment."""
from importlib.resources import files
import json

from environments import environment_package
from perception.modalities import observation_profile
from control.profiles import control_profile
from demonstrations.common import reference_enabled


def evaluation_prompt(args):
    specific = files(environment_package(args.benchmark)).joinpath('prompts')
    observation = observation_profile(
        args.benchmark, getattr(args, 'tactile_mode', None), getattr(args, 'measured_depth', None))
    parts = [specific.joinpath('control.md').read_text(encoding='utf-8')]
    if args.depth_estimation:
        parts.append(specific.joinpath('depth_estimation.md').read_text(encoding='utf-8'))
    if reference_enabled(args):
        parts.append(specific.joinpath('reference.md').read_text(encoding='utf-8'))
    parts.append('Current benchmark control capabilities:\n' + json.dumps(control_profile(args.benchmark)))
    parts.append('Observation capabilities:\n' + json.dumps(observation))
    if observation['measured_depth']:
        parts.append(specific.joinpath('measured_depth.md').read_text(encoding='utf-8'))
    return '\n'.join(parts)
