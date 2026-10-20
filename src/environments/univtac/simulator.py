"""UniVTAC entry point; start Isaac Lab before loading native task modules."""
from ..simulator import run


def start_app(args):
    from isaaclab.app import AppLauncher
    return AppLauncher(headless=True, enable_cameras=True, device=f'cuda:{args.device_id}', anti_aliasing=1,
        kit_args='--/plugins/carb.tasking.plugin/threadCount=4 --/plugins/omni.tbb.globalcontrol/maxThreadCount=4').app


def create_native(args):
    from .native import UniVTACNative
    return UniVTACNative(args)


def main(argv=None):
    run('univtac', create_native, start_app=start_app, argv=argv)


if __name__ == '__main__':
    main()
