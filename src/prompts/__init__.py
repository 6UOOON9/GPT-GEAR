"""Compose shared policy rules and the selected environment's prompt assets."""
from importlib.resources import files
import json

from environments import environment_package
from perception.modalities import observation_profile
from control.profiles import control_profile
from demonstrations.common import reference_enabled


def evaluation_prompt(args):
    shared = files(__package__)
    specific = files(environment_package(args.benchmark)).joinpath('prompts')
    parts = [shared.joinpath('control.md').read_text(encoding='utf-8')]
    if args.depth_estimation:
        parts.append(shared.joinpath('depth_estimation.md').read_text(encoding='utf-8'))
    if reference_enabled(args):
        parts.append(shared.joinpath('reference.md').read_text(encoding='utf-8'))
    parts.append('Current benchmark control capabilities:\n' + json.dumps(control_profile(args.benchmark)))
    parts.append('Observation capabilities:\n' + json.dumps(observation_profile(
        args.benchmark, getattr(args, 'tactile_mode', None), getattr(args, 'measured_depth', None))))
    parts.append(specific.joinpath('control.md').read_text(encoding='utf-8'))
    if getattr(args, 'measured_depth', False):
        parts.append(specific.joinpath('measured_depth.md').read_text(encoding='utf-8'))
    return '\n'.join(parts)
