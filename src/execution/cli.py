"""Public command dispatcher; simulator and reference dependencies are lazy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
from environments.benchmarks import BENCHMARKS, TASKS


def doctor(argv):
    from execution.config import parse_args
    from execution.launcher import preflight_mcp
    from environments.backends import get_backend
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument('--task')
    selector.add_argument('--benchmark', required=True, choices=BENCHMARKS)
    if '-h' in argv or '--help' in argv:
        print('Usage: gpt-gear doctor --benchmark {robodojo,libero-plus,libero-geomotion,robocasa-gr1,univtac,robotwin} --env-root PATH --sim-python PATH [--task TASK] [run options]')
        return 0
    selected, rest = selector.parse_known_args(argv)
    task = selected.task or dict(robodojo='align_blocks', **{'libero-plus':'libero_spatial/0', 'libero-geomotion':'libero_rp/0', 'robocasa-gr1':TASKS['robocasa-gr1'][0], 'univtac':'insert_HDMI', 'robotwin':'adjust_bottle'})[selected.benchmark]
    args = parse_args([task, str(Path.cwd() / '.cache/doctor-unused'),
                       '--benchmark', selected.benchmark, *rest])
    backend = get_backend(args.benchmark)
    info = backend.preflight(args)
    info['mcp'] = preflight_mcp(args)
    names = {
        'robodojo': ('isaaclab', 'isaacsim', 'numpy', 'PIL', 'omegaconf', 'curobo'),
        'libero-geomotion': ('geomotion', 'libero', 'robosuite', 'mujoco', 'numpy', 'PIL', 'torch', 'bddl', 'wand', 'skimage'),
        'libero-plus': ('libero', 'robosuite', 'mujoco', 'numpy', 'PIL', 'torch', 'bddl', 'wand', 'skimage'),
        'robocasa-gr1': ('robocasa', 'robosuite', 'mujoco', 'mink', 'numpy', 'PIL', 'h5py', 'scipy'),
        'robotwin': ('sapien', 'torch', 'numpy', 'PIL', 'yaml', 'envs'),
        'univtac': ('isaaclab', 'isaacsim', 'torch', 'uipc', 'numpy', 'PIL'),
    }[args.benchmark]
    script = 'import importlib.util,json,sys; print(json.dumps({"python":sys.version,"modules":{n:bool(importlib.util.find_spec(n)) for n in ' + repr(names) + '}}))'
    check = subprocess.run([str(args.sim_python), '-c', script], env=backend.environment(args),
                           cwd=args.env_root, capture_output=True, text=True, check=True, timeout=60)
    info['simulator'] = json.loads(check.stdout)
    if not all(info['simulator']['modules'].values()):
        raise ValueError(f'missing simulator dependencies: {info["simulator"]}')
    if args.benchmark == 'robocasa-gr1':
        # Metadata validation is read-only and does not construct a renderer or robot.
        script = ('from environments.robocasa_gr1.environment import environment_metadata, validate_controller; '
                  'import sys; validate_controller(environment_metadata(sys.argv[1], sys.argv[2])["env_kwargs"])')
        subprocess.run([str(args.sim_python), '-c', script, args.task, str(args.data_root)],
                       env=backend.environment(args), cwd=args.env_root, check=True, timeout=60)
    exe = shutil.which('codex')
    if not exe:
        raise ValueError('codex executable is not on PATH')
    info['codex_version'] = subprocess.check_output([exe, '--version'], text=True, timeout=15).strip()
    info['authentication'] = 'not checked; the episode uses the current user configuration'
    print(json.dumps(info, indent=2))
    return 0


def grouped_outcomes(rows, benchmark, field):
    """Summarize an environment's experimental conditions using valid episodes."""
    groups = {}
    for row in rows:
        if row.get('benchmark') != benchmark:
            continue
        value = (row.get('identity') or {}).get(field)
        counts = groups.setdefault(value, dict(success=0, task_failure=0, invalid=0, runtime_error=0))
        counts[row['status']] = counts.get(row['status'], 0) + 1
    for counts in groups.values():
        valid = counts['success'] + counts['task_failure']
        counts.update(valid_episodes=valid, success_rate=counts['success']/valid if valid else None)
    return groups


def summarize(argv):
    from execution.batch import classify, attempt_paths
    p = argparse.ArgumentParser(description='Read official results; latest queue attempt per episode')
    p.add_argument('output', type=Path)
    args = p.parse_args(argv)
    root = args.output.resolve()
    if not root.is_dir():
        raise ValueError('output directory does not exist')
    if (root / 'queue.json').is_file():
        outputs = []
        for job in json.loads((root / 'queue.json').read_text()):
            attempts = attempt_paths(root / job['id'])
            outputs.append((attempts[-1] if attempts else root / job['id'] / 'attempt-0001', bool(attempts), job))
    else:
        candidates = {p.parent for name in ('result.json', 'launcher.json', 'session.json') for p in root.rglob(name)}
        for sidecar in root.rglob('*.launcher.json'):
            candidates.add(Path(str(sidecar)[:-len('.launcher.json')]))
        outputs = [(p, True, None) for p in sorted(candidates)]
    rows = []
    for output, attempted, job in outputs:
        status = classify(output) if attempted else 'pending'
        row = dict(output=str(output), status=status)
        if job is not None:
            row.update(benchmark=job['host']['benchmark'], identity={k: job[k] for k in ('task', 'seed', 'tactile_mode', 'measured_depth', 'task_config') if k in job})
        try:
            result = json.loads((output / 'result.json').read_text())
            row.update(benchmark=result.get('benchmark', row.get('benchmark')),
                       identity=result.get('identity', row.get('identity')))
            if status in ('success', 'task_failure'):
                row['score'] = result['official_result'].get('score')
            metrics = output / 'action_metrics.json'
            if metrics.is_file():
                row['action_metrics'] = json.loads(metrics.read_text()).get('summary')
        except (OSError, ValueError, KeyError):
            pass
        rows.append(row)
    counts = Counter(row['status'] for row in rows)
    valid = counts['success'] + counts['task_failure']
    groups = {}
    for benchmark in BENCHMARKS:
        selected = [r for r in rows if r.get('benchmark') == benchmark]
        if not selected:
            continue
        successes = sum(r['status'] == 'success' for r in selected)
        n = sum(r['status'] in ('success', 'task_failure') for r in selected)
        scores = [r['score'] for r in selected if type(r.get('score')) in (int, float)]
        groups[benchmark] = dict(valid_episodes=n, success_rate=successes/n if n else None,
                                 mean_score=sum(scores)/len(scores) if scores else None)
    modes = grouped_outcomes(rows, 'univtac', 'tactile_mode')
    configurations = grouped_outcomes(rows, 'robotwin', 'task_config')
    print(json.dumps(dict(robotwin_task_configs=configurations, univtac_tactile_modes=modes, counts=dict(counts), valid_episodes=valid,
        success_rate=counts['success'] / valid if valid else None,
        benchmarks=groups, episodes=rows), indent=2))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = ('doctor', 'run', 'queue', 'reference', 'summarize')
    if not argv or argv[0] in ('-h', '--help'):
        print('Usage: gpt-gear {' + ','.join(commands) + '} ...')
        return 0
    command, rest = argv[0], argv[1:]
    try:
        if command == 'run':
            from execution.launcher import main as launch
            return launch(rest)
        if command == 'doctor':
            return doctor(rest)
        if command == 'queue':
            from execution.batch import main as run_queue
            return run_queue(rest)
        if command == 'summarize':
            return summarize(rest)
        if command == 'reference':
            if rest and rest[0] == 'prepare':
                from demonstrations.reference import main as prepare_reference
                return prepare_reference(rest[1:]) or 0
            if not rest or rest[0] in ('-h', '--help'):
                print('Usage: gpt-gear reference {annotate,prepare} ...')
                return 0
            if rest[0] != 'annotate':
                raise ValueError('unknown reference command')
            from demonstrations.video_to_steps import main as annotate
            return annotate(rest[1:]) or 0
        raise ValueError(f'unknown command {command}')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'gpt-gear: {exc}', file=sys.stderr)
        return 2
