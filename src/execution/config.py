"""Shared run configuration and validation; standard-library dependencies only."""
import argparse
import math
from pathlib import Path
import sys

from environments.benchmarks import BENCHMARKS, episode_options, validate_task
from perception.depth import boolean_string
from demonstrations.media import positive_fps
from demonstrations.common import reference_modalities

MCP_PYTHON = Path(sys.executable)
# Keep reference frames on the caller's data disk, not the system /tmp.
REFERENCE_TEMP_ROOT = Path.cwd() / '.cache/gpt-gear'
FINALIZE_GRACE = 120.0


def episode_settings(benchmark, values):
    """Normalize settings shared by CLI runs and JSON queue episodes."""
    result = episode_options(benchmark, values)
    seed = values.get('seed', 0)
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError('seed must fit uint32')
    depth = values.get('depth_estimation', not result.get('measured_depth', False))
    if type(depth) is not bool:
        raise ValueError('depth_estimation must be boolean')
    if result.get('measured_depth') and depth:
        raise ValueError('measured depth and estimation are mutually exclusive')
    return dict(result, seed=seed, depth_estimation=depth)


def reference_settings(*, video=None, trajectory=None, text=None, mode=None, fps=None):
    """Validate reference combinations and return normalized sampling settings."""
    if video is None and (mode is not None or fps is not None):
        raise ValueError('reference sampling options require --reference-video')
    reference_modalities(video=video, trajectory=trajectory, text=text)
    mode = 'sequence' if mode is None else mode
    if mode not in ('endpoints', 'sequence'):
        raise ValueError('reference mode must be endpoints or sequence')
    if fps is not None and mode != 'sequence':
        raise ValueError('--reference-fps is only valid with --reference-mode sequence')
    if fps is not None and (type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0):
        raise ValueError('reference fps must be a finite positive number')
    return mode, 1.0 if fps is None else fps


def nonnegative_integer(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('must be a nonnegative integer') from None
    if number < 0:
        raise argparse.ArgumentTypeError('must be a nonnegative integer')
    return number


def positive_seconds(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('must be a finite positive number') from None
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Run one simulation episode with a fresh Codex policy session.',
        allow_abbrev=False)
    parser.add_argument('task')
    parser.add_argument('output', type=Path)
    parser.add_argument('--benchmark', choices=BENCHMARKS, required=True)
    parser.add_argument('--env-root', type=Path, required=True)
    parser.add_argument('--init-state-index', type=nonnegative_integer)
    parser.add_argument('--max-native-steps', type=nonnegative_integer)
    parser.add_argument('--image-size', type=nonnegative_integer)
    parser.add_argument('--sim-python', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, default=REFERENCE_TEMP_ROOT)
    parser.add_argument('--seed', type=nonnegative_integer, default=0)
    parser.add_argument('--device-id', '--device_id', dest='device_id', type=nonnegative_integer, default=0)
    parser.add_argument('--port', type=int, default=8092)
    for key in ('connect', 'idle', 'request'):
        parser.add_argument('--codex_' + key + '_timeout', type=positive_seconds, default=600.)
    parser.add_argument('--codex-model')
    parser.add_argument('--depth-estimation', type=boolean_string, default=None)
    parser.add_argument('--reference-video', type=Path)
    parser.add_argument('--reference-text', type=Path)
    parser.add_argument('--trajectory', type=Path)
    parser.add_argument('--reference-mode', choices=('endpoints', 'sequence'), default=None)
    parser.add_argument('--reference-fps', type=positive_fps, default=None)
    parser.add_argument('--layout-id', dest='layout_id',
                        type=nonnegative_integer, default=None,
                        help='Select one layout variant within the evaluation seed')
    parser.add_argument('--codex-mcp-python', type=Path, default=MCP_PYTHON)
    parser.add_argument('--codex-startup-timeout', type=positive_seconds, default=600.)
    selector = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    selector.add_argument('--benchmark')
    selected, _ = selector.parse_known_args(argv)
    parser.add_argument('--robosuite-root', type=Path)
    parser.add_argument('--data-root', type=Path)
    if selected.benchmark == 'robotwin':
        parser.add_argument('--task-config', choices=('clean', 'random'))
    if selected.benchmark == 'robocasa-gr1':
        parser.add_argument('--measured-depth', type=boolean_string)
    if selected.benchmark == 'univtac':
        from environments.benchmarks import TACTILE_MODES
        parser.add_argument('--tactile-mode', choices=TACTILE_MODES)
        for key in ('max-policy-actions', 'control-decimation', 'image-width', 'image-height'):
            parser.add_argument('--' + key, type=nonnegative_integer)
    args = parser.parse_args(argv)
    try:
        vars(args).update(episode_settings(
            args.benchmark, {key: value for key, value in vars(args).items() if value is not None}))
        validate_task(args.benchmark, args.task)
        for key in ('robosuite_root', 'data_root'):
            value = getattr(args, key, None)
            if args.benchmark == 'robocasa-gr1':
                if value is None:
                    raise ValueError('--' + key.replace('_', '-') + ' is required for robocasa-gr1')
                setattr(args, key, value.expanduser().resolve())
            elif value is not None:
                raise ValueError(key + ' requires robocasa-gr1')
        args.reference_mode, args.reference_fps = reference_settings(
            video=args.reference_video, trajectory=args.trajectory, text=args.reference_text,
            mode=args.reference_mode, fps=args.reference_fps)
    except ValueError as exc:
        parser.error(str(exc))
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    args.env_root = args.env_root.expanduser().resolve()
    args.sim_python = args.sim_python.expanduser().absolute()
    args.cache_dir = args.cache_dir.expanduser().resolve()
    for name in ('reference_video', 'reference_text', 'trajectory'):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).expanduser().resolve())
    args.reference_cache = None
    args.reference_manifest_sha256 = None
    args.drain_timeout = max(args.codex_connect_timeout, args.codex_idle_timeout,
                             args.codex_request_timeout) + FINALIZE_GRACE
    args.output = args.output.expanduser().resolve()
    # Do not resolve the venv symlink: invoking the base interpreter loses its dependencies.
    args.codex_mcp_python = args.codex_mcp_python.expanduser().absolute()
    return args
