"""Read-only configuration validation in the selected simulation interpreter."""
import copy
import hashlib
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import sys

import yaml

from .backend import CONFIGS


def load_configuration(root, task, task_config):
    root = Path(root)
    config_dir = root / 'env_cfg/task_config'
    config = yaml.safe_load((config_dir / (CONFIGS[task_config] + '.yml')).read_text())
    embodiments = yaml.safe_load((config_dir / '_embodiment_config.yml').read_text())
    selected = config.get('embodiment') if isinstance(config, dict) else None
    # The supplied integration implements a shared dual-arm embodiment only.
    if not isinstance(selected, list) or len(selected) != 1 or selected[0] not in embodiments:
        raise ValueError('RoboTwin requires one shared dual-arm embodiment')
    robot_path = (root / embodiments[selected[0]]['file_path']).resolve()
    robot_config_path = robot_path / 'config.yml'
    robot_config = yaml.safe_load(robot_config_path.read_text())
    if not isinstance(robot_config, dict) or not isinstance(config.get('data_type'), dict):
        raise ValueError('invalid RoboTwin robot/data_type configuration')
    assets = {}
    for key in ('urdf_path', 'srdf_path'):
        value = robot_config.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError(f'invalid RoboTwin {key}')
            path = (robot_path / value).resolve()
            if not path.is_file():
                raise ValueError(f'missing RoboTwin robot asset: {path}')
            assets[key] = str(path)
    for side in ('left', 'right'):
        config[side + '_robot_file'] = str(robot_path)
        config[side + '_embodiment_config'] = copy.deepcopy(robot_config)
    description = json.loads((root / 'description/task_instruction' / (task + '.json')).read_text())
    if not isinstance(description.get('full_description'), str) or not description['full_description'].strip():
        raise ValueError('missing RoboTwin task instruction')
    metadata = dict(robot_root=str(robot_path), robot_config=str(robot_config_path), robot_assets=assets,
                    robot_config_sha256=hashlib.sha256(robot_config_path.read_bytes()).hexdigest())
    return config, metadata


def main():
    root, task, task_config = sys.argv[1:]
    _, metadata = load_configuration(root, task, task_config)
    names = ('sapien', 'torch', 'numpy', 'PIL', 'yaml')
    missing = [name for name in names if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError(f'missing RoboTwin dependencies: {missing}')
    from execution.video import check_encoder
    metadata.update(encoder=check_encoder(), python=sys.version, executable=sys.executable,
        dependencies={name: importlib.metadata.version(name)
                      for name in ('sapien', 'torch', 'numpy', 'Pillow', 'PyYAML')})
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
