"""GeoMotion extension registration precedes the shared simulator bootstrap."""
from ..simulator import run


def prepare_environment(args, host):
    args.suite, args.task_id = 'libero_rp', host['identity']['task_id']
    args.geomotion_identity = host['identity']
    from geomotion.runtime import configure
    configure(config_dir=args.output / 'libero_config')
    import geomotion
    geomotion.get_suite()


def create_native(args):
    from .native import GeoMotionNative
    return GeoMotionNative(args)


def main(argv=None):
    run('libero-geomotion', create_native, prepare_environment=prepare_environment, argv=argv)


if __name__ == '__main__':
    main()
