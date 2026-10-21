"""Stdlib-only task registry and benchmark-specific option validation."""
import json
import re
from pathlib import Path

BENCHMARKS = ('robodojo', 'libero-plus', 'libero-geomotion', 'robocasa-gr1', 'univtac', 'robotwin')
TASKS = json.loads(Path(__file__).with_name('tasks.json').read_text())
TACTILE_MODES = ('none', 'image', 'force', 'image-force')
DEFAULTS = {
    'robotwin': dict(task_config='clean', max_native_steps=1000, image_size=256),
    'robodojo': dict(layout_id=0),
    'libero-plus': dict(init_state_index=0, max_native_steps=600, image_size=256),
    'libero-geomotion': dict(init_state_index=0, max_native_steps=4000, image_size=256),
    'robocasa-gr1': dict(max_native_steps=1000, image_size=256, measured_depth=True),
    'univtac': dict(max_native_steps=400, max_policy_actions=40, control_decimation=6,
                    image_width=480, image_height=270, tactile_mode='force'),
}
PATH_OPTIONS = {'robocasa-gr1': ('robosuite_root', 'data_root')}
EPISODE_OPTIONS = set().union(*(set(v) for v in DEFAULTS.values()))


def episode_options(benchmark, values):
    if benchmark not in BENCHMARKS:
        raise ValueError('unknown benchmark')
    supplied = {k: v for k, v in values.items() if k in EPISODE_OPTIONS and v is not None}
    invalid = set(supplied) - set(DEFAULTS[benchmark])
    if invalid:
        raise ValueError(f'options not supported by {benchmark}: {sorted(invalid)}')
    result = dict(DEFAULTS[benchmark], **supplied)
    for key, value in result.items():
        if key == 'task_config':
            if value not in ('clean', 'random'):
                raise ValueError('task_config must be clean or random')
        elif key == 'tactile_mode':
            if value not in TACTILE_MODES:
                raise ValueError('invalid UniVTAC tactile mode')
        elif key == 'measured_depth':
            if type(value) is not bool:
                raise ValueError('measured_depth must be boolean')
        elif type(value) is not int or value < (0 if key in ('layout_id', 'init_state_index') else 1):
            raise ValueError(f'invalid {key}')
    for key in ('image_size', 'image_width', 'image_height'):
        if key in result and not 32 <= result[key] <= 2048:
            raise ValueError(f'{key} must be 32..2048')
    if benchmark in ('libero-plus', 'robocasa-gr1') and result['max_native_steps'] < 11:
        raise ValueError('max-native-steps must be >=11 (includes 10 initialization steps)')
    if benchmark == 'libero-geomotion' and result['init_state_index'] != 0:
        raise ValueError('LIBERO-GeoMotion has only fixed init-state-index 0')
    return result


def validate_task(benchmark, task):
    if benchmark == 'robotwin' and (not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9_]+', task)):
        raise ValueError('invalid RoboTwin task name')
    if benchmark in TASKS and task not in TASKS[benchmark]:
        raise ValueError(f'unknown {benchmark} task: {task}')
