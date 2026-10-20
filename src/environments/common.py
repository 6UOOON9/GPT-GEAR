"""Shared backend launch and reference-cache plumbing; stdlib only."""
import os
from pathlib import Path
import shutil
import subprocess

from execution import runtime
from environments.benchmarks import DEFAULTS, PATH_OPTIONS
from . import environment_package


def source_info(root, baseline=None):
    if not root.is_dir():
        raise ValueError(f'missing simulation repository: {root}')
    def git(*parts):
        return subprocess.check_output(['git', '-C', str(root), *parts], text=True, stderr=subprocess.PIPE).strip()
    commit = git('rev-parse', 'HEAD')
    dirty = git('diff', 'HEAD', '--name-only')
    if baseline and (commit != baseline or dirty):
        raise ValueError(f'{root} must be clean at {baseline}')
    return dict(root=str(root), commit=commit, tracked_changes=dirty.splitlines(),
                untracked=git('ls-files', '--others', '--exclude-standard').splitlines())


def process_environment(args, *extra_roots):
    env = runtime.thread_environment()
    roots = (runtime.SOURCE_ROOT, args.env_root, *extra_roots)
    env.update(PYTHONPATH=os.pathsep.join(map(str, roots)),
               PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
               XDG_CACHE_HOME=str(args.cache_dir / 'xdg'),
               NUMBA_CACHE_DIR=str(args.cache_dir / 'numba'))
    return env


def vendor_environment(env, root, egl_path):
    # Use checkout-local vendor files when available; otherwise keep discovery.
    for key, relative in (('__EGL_VENDOR_LIBRARY_FILENAMES', egl_path),
                          ('VK_ICD_FILENAMES', 'scripts/nvidia_icd.json')):
        path = root / relative
        if path.is_file():
            env.setdefault(key, str(path))
    return env


def launch_spec(backend, args):
    command = [str(args.sim_python), '-u', '-m', environment_package(backend.name) + '.simulator',
               args.task, str(args.output), '--benchmark', backend.name,
               '--env-root', str(args.env_root), '--sim-python', str(args.sim_python)]
    for key in ('seed', 'device_id', 'port', *DEFAULTS[backend.name],
                *PATH_OPTIONS.get(backend.name, ()), 'depth_estimation'):
        value = getattr(args, key)
        command += ['--' + key.replace('_', '-'), str(value).lower() if isinstance(value, bool) else str(value)]
    for key in ('connect', 'idle', 'request'):
        command += ['--codex_' + key + '_timeout', str(getattr(args, 'codex_' + key + '_timeout'))]
    env = backend.environment(args)
    for key in ('SIM_REFERENCE_CACHE', 'SIM_REFERENCE_SHA256'):
        env.pop(key, None)
    if args.reference_cache:
        env.update(SIM_REFERENCE_CACHE=str(args.reference_cache),
                   SIM_REFERENCE_SHA256=args.reference_manifest_sha256)
    return dict(command=command, cwd=str(args.env_root), env=env)


def prepare_reference(args):
    """Validate and copy the selected reference into a fresh episode directory."""
    from demonstrations.cache import load_manifest
    args.reference_manifest_sha256 = os.environ.get('SIM_REFERENCE_SHA256')
    cache = os.environ.get('SIM_REFERENCE_CACHE')
    if bool(cache) != bool(args.reference_manifest_sha256):
        raise ValueError('reference cache/digest mismatch')
    if cache:
        manifest = load_manifest(Path(cache).parent, args.reference_manifest_sha256)
        if manifest['benchmark'] != args.benchmark:
            raise ValueError('reference benchmark mismatch')
        shutil.copytree(cache, args.output / 'reference')
        load_manifest(args.output, args.reference_manifest_sha256)
