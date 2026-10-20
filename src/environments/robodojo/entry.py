"""Integration helpers kept importable without Isaac Sim."""
import atexit
import math
from pathlib import Path
import shutil
import time

from execution.artifacts import write_json


def prepare(args):
    """Validate before launching the expensive simulator; reserve a fresh output."""
    if args.num_envs != 1 or args.env_cfg_type != 'arx_x5':
        raise ValueError('Codex control requires one arx_x5 environment')
    if args.host != '127.0.0.1':
        raise ValueError('Codex control is local-only: use --host 127.0.0.1')
    if not args.codex_output:
        raise ValueError('--codex_output must be a fresh output directory')
    layout_id = getattr(args, 'codex_layout_id', None)
    if layout_id is not None:
        if isinstance(layout_id, bool) or not isinstance(layout_id, int) or layout_id < 0:
            raise ValueError('--codex_layout_id must be a nonnegative integer')
        from env.global_configs import ASSETS_PATH, BENCHMARK
        layout = (Path(ASSETS_PATH) / 'Eval_Layout' / BENCHMARK / args.env_cfg_type
                  / str(args.seed) / f'{args.task_name}_{layout_id}.json')
        if not layout.is_file():
            raise ValueError(
                f'layout {layout_id} does not exist for task {args.task_name!r} '
                f'in evaluation seed {args.seed}: {layout}'
            )
    for name in ('connect_timeout', 'idle_timeout', 'request_timeout'):
        value = getattr(args, 'codex_' + name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Codex timeouts must be finite and positive')
    from protocol.contracts import capabilities
    from demonstrations.cache import load_manifest
    caps = capabilities(args.codex_depth_estimation, args.codex_reference_manifest_sha256)
    cache = args.codex_reference_cache
    if bool(cache) != caps['reference_enabled']:
        raise ValueError('reference cache and digest must be provided together')
    if cache:
        cache = Path(cache).resolve(strict=True)
        if cache.name != 'reference':
            raise ValueError('reference cache must be a prepared reference directory')
        load_manifest(cache.parent, caps['reference_manifest_sha256'])
    path = Path(args.codex_output).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=False)
    args.codex_output = str(path)
    if cache:
        shutil.copytree(cache, path / 'reference', symlinks=True)
        load_manifest(path, caps['reference_manifest_sha256'])
    write_json(
        path / 'startup.json',
        dict(task_name=args.task_name, evaluation_seed=args.seed,
             layout_id=layout_id, started_at=time.time(), **caps),
    )

    def incomplete_exit():
        if not (path / 'result.json').exists():
            write_json(path / 'result.json', dict(
                format='sim-result-v1', benchmark='robodojo', task_success=None,
                identity=dict(task=args.task_name, seed=args.seed, layout_id=layout_id),
                complete=False, valid_for_success_rate=False, task_name=args.task_name,
                evaluation_seed=args.seed, layout_id=layout_id,
                stop_reason='process_exited_before_result', guidance='Inspect server startup log.'))
    atexit.register(incomplete_exit)


def run_single(env, simulation_app):
    """Keep native initialization/final scoring, but never recover an active rollout."""
    from utils.cluttered_generator import UnStableError
    output = Path(env.deploy_cfg['codex_output'])
    try:
        while env.env_seeds is not None:
            if getattr(env, 'physx_monitor_enabled', False):
                env._physx_get_monitor().reset()
            try:
                env.reset(seed=env.env_seeds)
            except UnStableError:
                if env.eval_cfg.get('layout_id') is not None:
                    raise
                # Invalid initial layouts are not evaluated; no Codex session exists yet.
                env.seed_manager.eval_step()
                env.close()
                env.env_seeds = env.seed_manager.get_seeds(max_count=1)
                continue
            env.run_eval()  # native reward preamble, control, scoring and video saving
            env.codex_control.complete(env.eval_result)
            return
        raise RuntimeError('no valid initial layout available')
    except BaseException as exc:
        layout_id = int(env.env_seeds[0]) if env.env_seeds else None
        write_json(output / 'result.json', dict(
            format='sim-result-v1', benchmark='robodojo', task_success=None,
            identity=dict(task=env.task_name, seed=int(env.eval_seed), layout_id=layout_id),
            complete=False, valid_for_success_rate=False, task_name=env.task_name,
            evaluation_seed=int(env.eval_seed), layout_id=layout_id, seed=layout_id,
            stop_reason='runtime_failure', error=f'{type(exc).__name__}: {exc}',
            official_save_dir=str(Path(env.save_dir).resolve())))
        raise
    finally:
        if env.codex_control is not None:
            env.codex_control.close()
        env.close()
        simulation_app.close()
