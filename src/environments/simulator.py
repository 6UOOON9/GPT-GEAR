"""Shared native owner-process bootstrap; --smoke checks interfaces without a model."""
import argparse
from contextlib import ExitStack
import importlib
import importlib.metadata
import os
from pathlib import Path
import signal
import sys

from environments.backends import get_backend
from execution.config import parse_args
from .common import prepare_reference


def checked_modules(args):
    pairs = get_backend(args.benchmark).module_roots(args)
    paths = {}
    for name, root in pairs:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f'{name} escaped selected checkout: {path}')
        paths[name] = str(path)
    return paths


def smoke(native, output):
    from execution.session import Session
    from execution.artifacts import write_json
    session = Session(native, output, depth_estimation=False)
    session.snapshot()
    state = native.observe()['robot_state']
    commands = []
    for arm in native.control_profile['arms']:
        command = dict(type='delta_pose', frame='environment', arm=arm, dpos=[0., 0., 0.], dquat=[1., 0., 0., 0.])
        if native.benchmark == 'univtac':
            command['gripper_position_m'] = state['robot0_gripper_position_m']
        commands.append(command)
    before = native.status()['action_count']
    outcome = native.execute(commands)
    if not outcome.get('success'):
        raise RuntimeError('smoke: native hold failed: ' + str(outcome.get('error')))
    if native.status()['action_count'] != before + 1:
        raise RuntimeError('smoke: native control step did not advance once')
    session.snapshot()
    final = native.finalize()
    if not final.get('video', {}).get('complete'):
        raise RuntimeError('smoke: episode video incomplete')
    write_json(output / 'smoke.json', dict(interface_check=True, benchmark=native.benchmark,
        identity=native.identity, capabilities=session.capabilities, status=native.status(),
        note='One hold step only; no model and no policy success-rate sample.'))
    write_json(output / 'result.json', dict(format='sim-result-v1', benchmark=native.benchmark,
        identity=native.identity, complete=True, valid_for_success_rate=False,
        task_success=None, stop_reason='interface_smoke_only', official_result={}))


def run(benchmark, create_native, *, prepare_environment=None, start_app=None, argv=None):
    selector = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    selector.add_argument('--smoke', action='store_true')
    selected, rest = selector.parse_known_args(argv)
    args = parse_args(rest)
    if args.benchmark != benchmark:
        raise ValueError(f'simulator requires --benchmark {benchmark}')
    backend = get_backend(args.benchmark)
    args.save_video = True
    args.output.mkdir(parents=True, exist_ok=False)
    app = native = session = None
    identity = dict(task=args.task, seed=args.seed)
    interrupted = False

    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        if session is not None:
            session.cancelled.set()
        else:
            raise KeyboardInterrupt('simulation startup interrupted')

    from execution.artifacts import write_json
    with ExitStack() as cleanup:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(sig, stop)
            cleanup.callback(signal.signal, sig, previous)
        try:
            host = backend.preflight(args)
            identity = host['identity']
            os.environ.update(backend.environment(args))
            os.chdir(args.env_root)
            for root in dict.fromkeys(root for _, root in backend.module_roots(args)):
                sys.path.insert(0, str(root))
            if prepare_environment is not None:
                prepare_environment(args, host)
            prepare_reference(args)
            if start_app is not None:
                app = start_app(args)
                cleanup.callback(app.close, wait_for_replicator=False)
            host.update(modules=checked_modules(args), python=sys.version, executable=sys.executable)
            host['dependencies'] = {name: importlib.metadata.version(name) for name in backend.dependencies}
            write_json(args.output / 'host.json', host)
            native = create_native(args)
            cleanup.callback(native.close)
            identity = native.identity
            write_json(args.output / 'startup.json', dict(benchmark=args.benchmark, identity=identity))
            if selected.smoke:
                smoke(native, args.output)
            else:
                from execution.session import Session
                session = Session(native, args.output, port=args.port, depth_estimation=args.depth_estimation,
                    reference_manifest_sha256=args.reference_manifest_sha256,
                    **{key + '_timeout': getattr(args, 'codex_' + key + '_timeout') for key in ('connect', 'idle', 'request')})
                cleanup.callback(session.close)
                if interrupted:
                    session.cancelled.set()
                session.run()
                session.complete()
        except BaseException as exc:
            write_json(args.output / 'result.json', dict(format='sim-result-v1', benchmark=args.benchmark,
                identity=identity, complete=False, valid_for_success_rate=False, task_success=None,
                stop_reason='runtime_failure' if session else 'startup_failure', error=f'{type(exc).__name__}: {exc}'))
            raise

