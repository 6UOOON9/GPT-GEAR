"""Host validation and launch configuration; stdlib only."""
import ast
import subprocess

from ..common import launch_spec, process_environment

LIBERO_BASELINE = '4976dc30028e805ff8094b55501d532c48fec182'


class Backend:
    name = 'libero-plus'
    dependencies = ('robosuite', 'mujoco', 'torch', 'numpy', 'Pillow')
    launch_spec = launch_spec

    def module_roots(self, args):
        return [(name, args.env_root) for name in (
            'libero.libero', 'libero.libero.envs.env_wrapper', 'libero.libero.benchmark')]

    def preflight(self, args):
        root = args.env_root
        def git(*parts):
            return subprocess.check_output(['git', '-C', str(root), *parts], text=True).strip()
        head = git('rev-parse', 'HEAD')
        if head != LIBERO_BASELINE or git('diff', 'HEAD', '--name-only'):
            raise ValueError('LIBERO-plus must be clean at ' + LIBERO_BASELINE)
        for name in ('assets', 'bddl_files', 'init_files'):
            if not (root / 'libero/libero' / name).is_dir():
                raise ValueError('missing LIBERO-plus resource: ' + name)
        return dict(root=str(root), commit=head, identity=self.resolve_task(args))

    def resolve_task(self, args):
        parts = args.task.split('/')
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError('LIBERO-plus task must be suite/task_id')
        suite, task_id = parts[0], int(parts[1])
        path = args.env_root / 'libero/libero/benchmark/libero_suite_task_map.py'
        tree = ast.parse(path.read_text())
        mapping = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'libero_task_map' for t in n.targets))
        if suite not in mapping or task_id >= len(mapping[suite]):
            raise ValueError('unknown LIBERO-plus task')
        return dict(task=f'{suite}/{task_id}', task_name=mapping[suite][task_id], suite=suite,
                    task_id=task_id, seed=args.seed, init_state_index=args.init_state_index)

    def environment(self, args):
        env = process_environment(args)
        env.update(LIBERO_CONFIG_PATH=str(args.output / 'libero_config'), MUJOCO_GL='egl',
                   PYOPENGL_PLATFORM='egl', MUJOCO_EGL_DEVICE_ID=str(args.device_id))
        return env

