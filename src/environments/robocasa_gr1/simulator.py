"""RoboCasa GR1 simulation entry point."""
from ..simulator import run


def create_native(args):
    from .native import RobocasaNative
    return RobocasaNative(args)


def main(argv=None):
    run('robocasa-gr1', create_native, argv=argv)


if __name__ == '__main__':
    main()
