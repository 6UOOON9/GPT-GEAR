"""Host validation and launch configuration; stdlib only."""
from . import runtime


class Backend:
    name = 'robodojo'

    def preflight(self, args):
        info = runtime.host_info(args.env_root)
        info['identity'] = self.resolve_task(args)
        return info

    def resolve_task(self, args):
        runtime.check_layout(args.env_root, args.task, args.seed, args.layout_id)
        return dict(task=args.task, seed=args.seed, layout_id=args.layout_id)

    def environment(self, args):
        return runtime.process_environment(args.env_root, args.cache_dir)

    def launch_spec(self, args):
        command = [str(args.sim_python), '-u', '-m', 'environments.robodojo.simulator',
                   '--env-root', str(args.env_root), '--task_name', args.task,
                   '--env_cfg_type', 'arx_x5', '--num_envs', '1', '--policy_name', 'Codex',
                   '--device_id', str(args.device_id), '--port', str(args.port),
                   '--host', '127.0.0.1', '--seed', str(args.seed),
                   '--additional_info', 'codex_env_delta',
                   '--codex_output', str(args.output), '--codex_layout_id', str(args.layout_id),
                   '--enable_cameras', '--headless', '--kit_args',
                   '--enable isaacsim.replicator.behavior --enable isaacsim.sensors.camera']
        command += ['--depth-estimation', str(args.depth_estimation).lower()]
        if args.reference_cache:
            command += ['--codex_reference_cache', str(args.reference_cache),
                        '--codex_reference_manifest_sha256', args.reference_manifest_sha256]
        for key in ('connect', 'idle', 'request'):
            command += ['--codex_' + key + '_timeout', str(getattr(args, 'codex_' + key + '_timeout'))]
        return dict(command=command, cwd=str(args.env_root), env=self.environment(args))
