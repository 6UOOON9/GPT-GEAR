"""Serial, configuration-driven episodes; retries always use fresh directories."""
import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from environments.benchmarks import BENCHMARKS, DEFAULTS, EPISODE_OPTIONS, PATH_OPTIONS, validate_task
from execution.config import episode_settings, reference_settings


def classify(output):
    output = Path(output)
    try:
        result = json.loads((output / 'result.json').read_text())
        launcher = json.loads((output / 'launcher.json').read_text())
    except (OSError, ValueError):
        return 'runtime_error'
    if not result.get('complete') or not launcher.get('complete'):
        return 'runtime_error'
    if not result.get('valid_for_success_rate'):
        return 'invalid'
    if result.get('format') != 'sim-result-v1' or result.get('benchmark') not in BENCHMARKS:
        return 'runtime_error'
    if type(result.get('task_success')) is not bool or not isinstance(result.get('official_result'), dict):
        return 'runtime_error'
    return 'success' if result['task_success'] else 'task_failure'


def load_jobs(path, *, env_root=None, sim_python=None):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    if data.get('version') != 2 or not isinstance(data.get('episodes'), list) or not data['episodes']:
        raise ValueError('queue requires version=2 and nonempty episodes')
    environments = data.get('environments')
    if not isinstance(environments, dict) or not environments:
        raise ValueError('queue requires named environments')
    if (env_root or sim_python) and len(environments) != 1:
        raise ValueError("CLI path overrides require exactly one environment")
    resolved = {}
    for name, env in environments.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or not isinstance(env, dict):
            raise ValueError('invalid environment')
        if (env.get('benchmark') not in BENCHMARKS or set(env) !=
                {'benchmark', 'env_root', 'sim_python', *PATH_OPTIONS.get(env.get('benchmark'), ())}):
            raise ValueError('environment requires benchmark, env_root and sim_python')
        value = dict(env)
        for key in ('env_root', 'sim_python', *PATH_OPTIONS.get(env['benchmark'], ())):
            if not isinstance(value[key], str) or not value[key]:
                raise ValueError('environment paths must be nonempty strings')
            override = env_root if key == 'env_root' else sim_python if key == 'sim_python' else None
            target = Path(override).expanduser().absolute() if override is not None else (path.parent / Path(value[key]).expanduser()).absolute()
            value[key] = str(target.resolve() if key != 'sim_python' else Path(os.path.normpath(target)))
        resolved[name] = value
    jobs, identities = [], set()
    allowed = {'environment', 'task', 'seed', 'depth_estimation', 'reference'} | EPISODE_OPTIONS
    for entry in data['episodes']:
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError('unknown episode option')
        job = dict(entry)
        if job.get('environment') not in resolved:
            raise ValueError('episode references unknown environment')
        job['host'] = dict(resolved[job['environment']])
        benchmark = job['host']['benchmark']
        task = job.get('task')
        pattern = r'[A-Za-z0-9_]+/[0-9]+' if benchmark in ('libero-plus', 'libero-geomotion') else r'[A-Za-z0-9_]+'
        if not isinstance(task, str) or not re.fullmatch(pattern, task):
            raise ValueError('invalid task identifier')
        if benchmark in ('libero-plus', 'libero-geomotion'):
            suite, task_id = task.split('/')
            task = job['task'] = f'{suite}/{int(task_id)}'
        validate_task(benchmark, task)
        # A JSON null is not a way to bypass benchmark option isolation.
        if (set(job) & EPISODE_OPTIONS) - set(DEFAULTS[benchmark]):
            raise ValueError('episode contains options for another benchmark')
        if any(job[k] is None for k in set(job) & EPISODE_OPTIONS):
            raise ValueError('episode options must not be null')
        job.update(episode_settings(benchmark, job))
        identity = dict(host=job['host'], task=task, seed=job['seed'],
                        initialization=job.get('layout_id', job.get('init_state_index')))
        if benchmark == 'robocasa-gr1':
            identity['measured_depth'] = job['measured_depth']
        if benchmark == 'univtac':
            identity['tactile_mode'] = job['tactile_mode']
        if benchmark == 'robotwin':
            identity['task_config'] = job['task_config']
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
        if digest in identities:
            raise ValueError('duplicate episode identity')
        identities.add(digest)
        job['id'] = f"{job['environment']}_{task.replace('/', '_')}_{digest}"
        reference = job.get('reference')
        if reference is not None:
            if not isinstance(reference, dict) or set(reference) - {'video', 'trajectory', 'text', 'mode', 'fps'}:
                raise ValueError('invalid reference options')
            reference = job['reference'] = dict(reference)
            for key in ('video', 'trajectory', 'text'):
                if key in reference:
                    if not isinstance(reference[key], str) or not reference[key]:
                        raise ValueError('reference paths must be nonempty strings')
                    reference[key] = str((path.parent / Path(reference[key]).expanduser()).resolve())
            if any(value is None for value in reference.values()):
                raise ValueError('reference options must not be null')
            reference_settings(**reference)
        else:
            job.pop('reference', None)
        jobs.append(job)
    return jobs


def attempt_paths(directory):
    paths = set()
    if directory.exists():
        for p in directory.iterdir():
            match = re.match(r'^(attempt-\d{4,})(?:$|\.)', p.name)
            if match:
                paths.add(directory / match[1])
    return sorted(paths, key=lambda p: int(p.name.split('-')[1]))


def command(job, output, args):
    host = job['host']
    result = [sys.executable, '-m', 'execution', 'run', job['task'], str(output),
              '--benchmark', host['benchmark'], '--env-root', host['env_root'],
              '--sim-python', host['sim_python'],
              '--codex-mcp-python', str(args.codex_mcp_python), '--cache-dir', str(args.cache_dir),
              '--seed', str(job['seed']), '--depth-estimation', str(job['depth_estimation']).lower(),
              '--device-id', str(args.device_id), '--port', str(args.port)]
    for key in sorted(EPISODE_OPTIONS):
        if key in job:
            result += ['--' + key.replace('_', '-'), str(job[key]).lower() if isinstance(job[key], bool) else str(job[key])]
    for key in PATH_OPTIONS.get(host['benchmark'], ()):
        result += ['--' + key.replace('_', '-'), host[key]]
    if args.codex_model:
        result += ['--codex-model', args.codex_model]
    mapping = {'video': '--reference-video', 'text': '--reference-text', 'trajectory': '--trajectory',
               'mode': '--reference-mode', 'fps': '--reference-fps'}
    for key, value in job.get('reference', {}).items():
        result.extend([mapping[key], str(value)])
    return result


def main(argv=None):
    from execution.config import MCP_PYTHON, REFERENCE_TEMP_ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--benchmark', choices=BENCHMARKS)
    p.add_argument('--env-root', type=Path)
    p.add_argument('--sim-python', type=Path)
    p.add_argument('--codex-mcp-python', type=Path, default=MCP_PYTHON)
    p.add_argument('--cache-dir', type=Path, default=REFERENCE_TEMP_ROOT)
    p.add_argument('--codex-model')
    p.add_argument('--device-id', type=int, default=0)
    p.add_argument('--port', type=int, default=8092)
    p.add_argument('--run', action='store_true', help='execute; otherwise only print the plan')
    p.add_argument('--retry-failed', action='store_true', help='new attempt for invalid/interrupted episodes')
    args = p.parse_args(argv)
    jobs = load_jobs(args.config, env_root=args.env_root, sim_python=args.sim_python)
    if args.benchmark and any(j['host']['benchmark'] != args.benchmark for j in jobs):
        raise ValueError('--benchmark disagrees with queue environments')
    args.output = args.output.expanduser().absolute()
    if args.output.is_symlink():
        raise ValueError('queue output cannot be a symlink')
    plans = []
    for job in jobs:
        directory = args.output / job['id']
        if directory.is_symlink():
            raise ValueError('episode group cannot be a symlink')
        attempts = attempt_paths(directory)
        prior = attempts[-1] if attempts else None
        status = classify(prior) if prior else 'new'
        run = prior is None or (status in ('runtime_error', 'invalid') and args.retry_failed)
        output = directory / f"attempt-{(int(prior.name.split('-')[1]) + 1) if prior else 1:04d}" if run else prior
        plans.append(dict(job=job, previous_status=status, execute=run, output=str(output), command=command(job, output, args)))
    if not args.run:
        print(json.dumps(plans, indent=2))
        return 0
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'queue interrupted by signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / '.queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = args.output / 'queue.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != jobs:
                raise ValueError('queue configuration changed; use a new output directory')
        else:
            with manifest.open('x') as file:
                json.dump(jobs, file, indent=2)
        errors = 0
        for plan in plans:
            if not plan['execute']:
                print(f"Skip {plan['job']['id']}: {plan['previous_status']}", flush=True)
                errors += plan['previous_status'] in ('runtime_error', 'invalid')
                continue
            output = Path(plan['output'])
            output.parent.mkdir(parents=True, exist_ok=True)
            with Path(str(output) + '.queue.log').open('x') as log:
                child = subprocess.Popen(plan['command'], stdout=log, stderr=subprocess.STDOUT)
                try:
                    rc = child.wait()
                except BaseException:
                    child.terminate()
                    try:
                        child.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                    raise
            status = classify(output)
            with (args.output / 'status.jsonl').open('a') as file:
                file.write(json.dumps(dict(output=str(output), exit_code=rc, status=status)) + '\n')
            errors += status in ('runtime_error', 'invalid') or rc != 0
            print(f"{plan['job']['id']}: {status}", flush=True)
    return int(bool(errors))
