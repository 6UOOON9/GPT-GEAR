"""LIBERO-plus configuration and factory for the shared simulator lifecycle."""
import json

from ..simulator import run


def prepare_environment(args, host):
    identity = host['identity']
    args.suite, args.task_id = identity['suite'], identity['task_id']
    config = args.output / 'libero_config'
    config.mkdir()
    root = args.env_root / 'libero/libero'
    # JSON is a YAML subset; avoid importing anything from an old editable checkout.
    (config / 'config.yaml').write_text(json.dumps(dict(
        benchmark_root=str(root), bddl_files=str(root / 'bddl_files'),
        init_states=str(root / 'init_files'), assets=str(root / 'assets'),
        datasets=str(args.output / 'unused_datasets'))))


def create_native(args):
    from .native import LiberoNative
    return LiberoNative(args)


def main(argv=None):
    run('libero-plus', create_native, prepare_environment=prepare_environment, argv=argv)


if __name__ == '__main__':
    main()
