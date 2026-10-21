"""Validate the standalone GeoMotion protocol without importing simulator libraries."""
import hashlib
import json
from pathlib import Path

from environments.benchmarks import validate_task
from ..common import launch_spec, process_environment


class Backend:
    name = 'libero-geomotion'
    dependencies = ('robosuite', 'mujoco', 'torch', 'numpy', 'Pillow', 'libero-geomotion')
    launch_spec = launch_spec

    def module_roots(self, args):
        return [(name, args.env_root) for name in (
            'geomotion', 'libero.libero', 'libero.libero.envs.env_wrapper',
            'libero_rotation_planning', 'libero_rotation_planning.benchmark')]

    def resolve_task(self, args):
        validate_task(self.name, args.task)
        tid = int(args.task.split('/')[1])
        base = args.env_root / 'libero_rotation_planning'
        tasks = json.loads((base / 'benchmark/task_manifest.json').read_text())
        if len(tasks) != 36 or [t['id'] for t in tasks] != list(range(36)):
            raise ValueError('invalid GeoMotion frozen task manifest')
        families = json.loads((args.env_root / 'geomotion/resources/task_families.json').read_text())
        family = next(f for f in families if tid in f['task_ids'])
        task = tasks[tid]
        if not isinstance(task['name'], str) or Path(task['name']).name != task['name']:
            raise ValueError('invalid GeoMotion task name')
        initial = base / 'init_files/libero_rp' / (task['name'] + '.pruned_init')
        return dict(task=args.task, task_name=task['name'], suite='libero_rp', task_id=tid,
                    family=family['panel'], family_name=family['name'], seed=args.seed,
                    init_state_index=0, init_sha256=hashlib.sha256(initial.read_bytes()).hexdigest())

    def preflight(self, args):
        if args.init_state_index != 0:
            raise ValueError('GeoMotion requires fixed initial state 0')
        root = args.env_root
        resources = root / 'geomotion/resources'
        protocol_path = resources / 'evaluation_protocol.json'
        protocol = json.loads(protocol_path.read_text())
        expected = dict(version='0.3.0', suite='libero_rp', task_order_index=0,
                        task_ids=list(range(36)), initial_state_indices=[0],
                        robots=['Panda'], controller='OSC_POSE', control_frequency_hz=20,
                        camera_names=['agentview', 'robot0_eye_in_hand'],
                        camera_resolution=[256, 256], max_episode_steps=4000,
                        action_dimension=7, action_range=[-1, 1], ignore_done=True)
        for key, value in expected.items():
            if protocol.get(key) != value:
                raise ValueError('unsupported GeoMotion evaluation protocol: ' + key)
        identity = self.resolve_task(args)
        base = root / 'libero_rotation_planning'
        for path in (root / 'libero/libero/assets', base / 'assets'):
            if not path.is_dir():
                raise ValueError('missing GeoMotion assets: ' + str(path))
        paths = [protocol_path, resources / 'task_families.json',
                 base / 'benchmark/task_manifest.json',
                 base / 'bddl_files/libero_rp' / (identity['task_name'] + '.bddl'),
                 base / 'init_files/libero_rp' / (identity['task_name'] + '.pruned_init')]
        digests = {}
        for path in paths:
            if not path.is_file() or not path.resolve().is_relative_to(root):
                raise ValueError('missing or invalid GeoMotion resource: ' + str(path))
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return dict(root=str(root), version=protocol['version'],
                    resource_sha256=digests, identity=identity)

    def environment(self, args):
        env = process_environment(args)
        env.update(LIBERO_CONFIG_PATH=str(args.output / 'libero_config'),
                   MUJOCO_GL='osmesa', PYOPENGL_PLATFORM='osmesa')
        return env
