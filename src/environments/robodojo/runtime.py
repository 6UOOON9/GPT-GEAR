"""Discovery and process configuration for the pinned RoboDojo checkout."""
from pathlib import Path
import os
import subprocess

from execution.runtime import SOURCE_ROOT, thread_environment

BASELINE = 'ee67a1468510da7624a089164402359f2afc72c8'


def host_info(root):
    root = Path(root).expanduser().resolve(strict=True)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE).strip()
    head = git('rev-parse', 'HEAD')
    if head != BASELINE:
        raise ValueError(f'unsupported RoboDojo commit {head}; expected {BASELINE}')
    if git('diff', 'HEAD', '--name-only', '--ignore-submodules=all'):
        raise ValueError('RoboDojo tracked sources differ from the supported baseline')
    for path in ('src/eval_client/eval_env.py', 'env/global_configs.py', 'env_cfg/arx_x5.yml', 'Assets'):
        if not (root / path).exists():
            raise ValueError(f'missing RoboDojo prerequisite: {path}')
    versions = {}
    for name in ('XPolicyLab', 'third_party/IsaacLab', 'third_party/curobo'):
        expected = git('rev-parse', 'HEAD:' + name)
        actual = subprocess.check_output(['git', '-C', str(root / name), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(root / name), 'diff', 'HEAD', '--name-only', '--ignore-submodules=all'], text=True).strip()
        if actual != expected or dirty:
            raise ValueError(f'{name} must be clean at pinned commit {expected}')
        versions[name] = actual
    return dict(root=str(root), commit=head, submodules=versions)

def python_paths(root):
    root = Path(root)
    # Override editable installations that may still point to another checkout.
    return [SOURCE_ROOT, root, root / 'XPolicyLab',
            *sorted((root / 'third_party/IsaacLab/source').glob('isaaclab*')),
            root / 'third_party/curobo']

def process_environment(root, cache):
    env = thread_environment()
    env['PYTHONPATH'] = os.pathsep.join(str(p) for p in python_paths(root))
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
    env['XDG_CACHE_HOME'] = str(Path(cache) / 'xdg')
    env['TORCH_EXTENSIONS_DIR'] = str(Path(cache) / 'torch_extensions')
    env['WARP_CACHE_PATH'] = str(Path(cache) / 'warp')
    # Each independent episode owns its run identity and never resumes another.
    for key in ('ROBODOJO_RUN_ID', 'ROBODOJO_FATAL_RESTART_COUNT', 'EVAL_NUM'):
        env.pop(key, None)
    return env

def check_layout(root, task, seed, layout):
    if not task or not all(c.isalnum() or c == '_' for c in task):
        raise ValueError('task must be a task identifier')
    if not (Path(root) / 'task/RoboDojo/tasks' / (task + '.py')).is_file():
        raise ValueError(f'unknown task: {task}')
    path = Path(root) / 'Assets/Eval_Layout/RoboDojo/arx_x5' / str(seed) / f'{task}_{layout}.json'
    if not path.is_file():
        raise ValueError(f'missing layout: {path}')
    return str(path)
