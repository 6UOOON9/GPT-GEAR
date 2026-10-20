"""RoboCasa GR1 host validation and launch configuration; stdlib only."""
from environments.benchmarks import validate_task
from ..common import launch_spec, process_environment, source_info, vendor_environment

ROBOCASA_BASELINE = '4840e671596f93ca03651524b9f72ffb1aadfeff'
ROBOSUITE_GR1_BASELINE = '51cc01785bab80ffeed20da15e67d7dd4140e76a'


class Backend:
    name = 'robocasa-gr1'
    dependencies = ('robosuite', 'mujoco', 'mink', 'numpy', 'h5py')
    launch_spec = launch_spec

    def resolve_task(self, args):
        validate_task(self.name, args.task)
        return dict(task=args.task, seed=args.seed, measured_depth=args.measured_depth)

    def module_roots(self, args):
        return [('robocasa', args.env_root), ('robosuite', args.robosuite_root)]

    def preflight(self, args):
        host = source_info(args.env_root, ROBOCASA_BASELINE)
        host['robosuite'] = source_info(args.robosuite_root, ROBOSUITE_GR1_BASELINE)
        for package, root in self.module_roots(args):
            if not (root / package / '__init__.py').is_file():
                raise ValueError(f'missing package {package} in {root}')
        dataset = args.data_root / f'{args.task}.hdf5'
        if not dataset.is_file():
            raise ValueError(f'missing GR1 environment metadata HDF5: {dataset}')
        host.update(environment_metadata=str(dataset), identity=self.resolve_task(args))
        return host

    def environment(self, args):
        env = process_environment(args, args.robosuite_root)
        env.update(MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl', MUJOCO_EGL_DEVICE_ID=str(args.device_id))
        return vendor_environment(env, args.env_root, 'local_setup/nvidia-egl.json')
