"""RoboTwin source selection and subprocess preflight; standard library only."""
import hashlib
import json
import subprocess

from environments.benchmarks import validate_task
from ..common import launch_spec, process_environment, source_info, vendor_environment

CONFIGS = {'clean': 'demo_clean', 'random': 'demo_randomized'}


class Backend:
    name = 'robotwin'
    dependencies = ('sapien', 'numpy', 'torch', 'Pillow', 'PyYAML')
    launch_spec = launch_spec

    def resolve_task(self, args):
        validate_task(self.name, args.task)
        return dict(task=args.task, seed=args.seed, task_config=args.task_config)

    def module_roots(self, args):
        return [('envs._base_task', args.env_root), ('envs.' + args.task, args.env_root)]

    def preflight(self, args):
        identity = self.resolve_task(args)
        host = source_info(args.env_root)
        for directory in ('envs', 'assets', 'env_cfg/task_config', 'description/task_instruction'):
            if not (args.env_root / directory).is_dir():
                raise ValueError(f'missing RoboTwin directory: {directory}')
        required = ('envs/_base_task.py', f'envs/{args.task}.py',
                    f'description/task_instruction/{args.task}.json',
                    f'env_cfg/task_config/{CONFIGS[args.task_config]}.yml',
                    'env_cfg/task_config/_embodiment_config.yml')
        host['source_sha256'] = {}
        for name in required:
            path = args.env_root / name
            if not path.is_file():
                raise ValueError(f'missing RoboTwin task/configuration: {path}')
            host['source_sha256'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        # PyYAML, encoder and simulator dependencies belong to the selected interpreter.
        check = subprocess.run([str(args.sim_python), '-m',
            'environments.robotwin.configuration', str(args.env_root),
            args.task, args.task_config], cwd=args.env_root, env=self.environment(args),
            capture_output=True, text=True, timeout=60)
        if check.returncode:
            raise ValueError('RoboTwin preflight failed: ' + check.stderr.strip())
        host.update(identity=identity, simulator=json.loads(check.stdout), expert_screening=False)
        return host

    def environment(self, args):
        env = process_environment(args, args.env_root / 'scripts')
        env.update(ROBOTWIN_ROOT=str(args.env_root), CUDA_VISIBLE_DEVICES=str(args.device_id))
        return vendor_environment(env, args.env_root, 'scripts/nvidia_egl.json')
