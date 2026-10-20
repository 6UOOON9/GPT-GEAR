"""RoboTwin simulation entry point, including the common --smoke check."""
from ..simulator import run


def create_native(args):
    from .native import RoboTwinNative
    return RoboTwinNative(args)


def main(argv=None):
    run('robotwin', create_native, argv=argv)


if __name__ == '__main__':
    main()
