"""UniVTAC host validation and launch configuration; stdlib only."""
import hashlib

from environments.benchmarks import validate_task
from ..common import launch_spec, process_environment, source_info, vendor_environment


class Backend:
    name = 'univtac'
    dependencies = ('isaacsim', 'isaaclab', 'torch', 'pyuipc', 'numpy')
    launch_spec = launch_spec

    def resolve_task(self, args):
        validate_task(self.name, args.task)
        return dict(task=args.task, seed=args.seed, tactile_mode=args.tactile_mode)

    def module_roots(self, args):
        return [('envs._base_task', args.env_root), ('envs.' + args.task, args.env_root)]

    def preflight(self, args):
        host = source_info(args.env_root)
        host['source_sha256'] = {}
        for name in ('envs/_base_task.py', f'envs/{args.task}.py'):
            path = args.env_root / name
            if not path.is_file():
                raise ValueError(f'missing UniVTAC source: {path}')
            host['source_sha256'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        host['identity'] = self.resolve_task(args)
        return host

    def environment(self, args):
        env = process_environment(args)
        env.update(UNIVTAC_ROOT=str(args.env_root), ISAACSIM_ACCEPT_EULA='Y', OMNI_KIT_ACCEPT_EULA='YES')
        return vendor_environment(env, args.env_root, 'scripts/nvidia_egl.json')
