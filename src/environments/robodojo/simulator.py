"""Standalone single-episode bootstrap, adapted from RoboDojo (MIT)."""
import argparse
from datetime import datetime
import importlib
import os
from pathlib import Path
import sys

from perception.depth import boolean_string
from environments.robodojo.entry import prepare, run_single
from environments.robodojo.runtime import host_info, python_paths

parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--env-root', type=Path, required=True)
parser.add_argument('--task_name', required=True)
parser.add_argument('--env_cfg_type', default='arx_x5')
parser.add_argument('--num_envs', type=int, default=1)
parser.add_argument('--device_id', type=int, default=0)
parser.add_argument('--policy_name', default='Codex')
parser.add_argument('--port', type=int, default=8092)
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--protocol', default='ws')
parser.add_argument('--policy_server_url', default='')
parser.add_argument('--additional_info', default='codex_env_delta')
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--codex_output', required=True)
parser.add_argument('--codex_layout_id', type=int, default=0)
for key in ('connect', 'idle', 'request'):
    parser.add_argument('--codex_' + key + '_timeout', type=float, default=600.)
parser.add_argument('--depth-estimation', dest='codex_depth_estimation', type=boolean_string, default=True)
parser.add_argument('--codex_reference_cache')
parser.add_argument('--codex_reference_manifest_sha256')
# The host location must be fixed before importing editable IsaacLab packages.
known, _ = parser.parse_known_args()
host = host_info(known.env_root)
sys.path[:0] = [str(p) for p in python_paths(host['root'])]
from isaaclab.app import AppLauncher
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
prepare(args_cli)
from env.global_configs import BENCHMARK, ROOT_DIR, ENV_CONFIG_PATH
from utils.load_file import load_yaml
task_registry = importlib.import_module(f'task.{BENCHMARK}.task_registry')
BENCHMARK_PATH = os.path.join(ROOT_DIR, 'task', BENCHMARK)
os.environ['ROBODOJO_RUN_ID'] = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
cfg_path = task_registry.task_config_path(os.path.join(BENCHMARK_PATH, 'config'), args_cli.task_name)
try:
    enable_monitor = bool((load_yaml(cfg_path) or {}).get('Articulation'))
except Exception:
    enable_monitor = True
if enable_monitor:
    from src.eval_client.physx_warning_monitor import get_monitor
    get_monitor().start(enabled=True)
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app
from omegaconf import OmegaConf
from utils.pipeline_utils import process_randomization, process_config, resolve_random_task_num_envs
from environments.robodojo.native import configure_observations
from environments.robodojo.adapter import create_eval_env


def main():
    task_name = args_cli.task_name
    num_envs = args_cli.num_envs
    eval_cfg_name = args_cli.env_cfg_type
    eval_cfg = load_yaml(os.path.join(ENV_CONFIG_PATH, eval_cfg_name + ".yml"))
    eval_cfg["task_name"] = task_name
    eval_cfg["num_envs"] = num_envs
    eval_cfg["device_id"] = args_cli.device_id
    eval_batch = False
    eval_cfg["eval_batch"] = eval_batch
    eval_cfg["policy_name"] = args_cli.policy_name
    eval_cfg["additional_info"] = args_cli.additional_info
    eval_cfg["seed"] = args_cli.seed
    eval_cfg["physx_monitor_enabled"] = enable_monitor

    eval_cfg["layout_id"] = args_cli.codex_layout_id
    deploy_cfg = {"codex_" + key: getattr(args_cli, "codex_" + key)
                  for key in ("output", "connect_timeout", "idle_timeout", "request_timeout",
                              "depth_estimation", "reference_manifest_sha256")}
    deploy_cfg["policy_name"] = args_cli.policy_name
    deploy_cfg["port"] = args_cli.port
    deploy_cfg["host"] = args_cli.host
    deploy_cfg["protocol"] = args_cli.protocol
    deploy_cfg["policy_server_url"] = args_cli.policy_server_url or f"ws://{args_cli.host}:{args_cli.port}"
    deploy_cfg["evaluation_id"] = os.environ["ROBODOJO_RUN_ID"]
    deploy_cfg["trial_id"] = f"{task_name}-{os.environ['ROBODOJO_RUN_ID']}"
    deploy_cfg["action_case_id"] = f"{task_name}_case"
    deploy_cfg["repeat_index"] = None
    env_cfg = OmegaConf.create(
        {
            "sim": load_yaml(os.path.join(ENV_CONFIG_PATH, "sim", eval_cfg["config"]["sim"] + ".yml")),
            "scene": load_yaml(
                os.path.join(
                    ENV_CONFIG_PATH,
                    "scene",
                    eval_cfg["config"]["scene"] + ".yml",
                )
            ),
            "camera": load_yaml(
                os.path.join(
                    ENV_CONFIG_PATH,
                    "camera",
                    eval_cfg["config"]["camera"] + ".yml",
                )
            ),
            "robot": load_yaml(
                os.path.join(
                    ENV_CONFIG_PATH,
                    "robot",
                    eval_cfg["config"]["robot"] + ".yml",
                )
            ),
            "task_env": load_yaml(task_registry.task_config_path(os.path.join(BENCHMARK_PATH, "config"), task_name)),
            "eval_cfg": eval_cfg,
            "deploy_cfg": deploy_cfg,
        }
    )
    capped_num_envs = resolve_random_task_num_envs(task_name, num_envs, env_cfg.sim)
    if capped_num_envs != num_envs:
        print(
            f"[main] Random task {task_name}: num_envs capped "
            f"{num_envs} -> {capped_num_envs} "
        )
    num_envs = capped_num_envs
    if not eval_batch and num_envs != 1:
        print(
            f"[main] eval_batch=false in XPolicyLab/policy/{args_cli.policy_name}/deploy.yml; "
            f"forcing num_envs {num_envs} -> 1"
        )
        num_envs = 1
    eval_cfg["num_envs"] = num_envs
    OmegaConf.update(env_cfg, "sim.scene.num_envs", num_envs, force_add=True)
    OmegaConf.update(env_cfg, "eval_cfg.num_envs", num_envs, force_add=True)
    configure_observations(env_cfg)
    env_cfg = process_randomization(env_cfg)
    env_cfg, eval_num = process_config(env_cfg, task_name=task_name)

    if os.environ.get("EVAL_NUM"):
        _env_eval_num = os.environ.get("EVAL_NUM")
        if str(_env_eval_num).lower() != "native":
            eval_num = min(int(_env_eval_num), int(eval_num))
    eval_num = 1
    eval_cfg["eval_num"] = eval_num
    env_cfg.eval_cfg.eval_num = 1

    OmegaConf.update(
        env_cfg,
        "camera.default_frequency",
        eval_cfg["observation"].get("collect_freq", 0),
        force_add=True,
    )

    env_cfg.sim.seed = [0 for _ in range(num_envs)]
    run_id = os.environ["ROBODOJO_RUN_ID"]
    resume_state = None
    env = create_eval_env(env_cfg, simulation_app, resume_state=resume_state)
    eval_time = env.success_nums + env.fail_nums
    if eval_time >= eval_num:
        # Already complete on resume - nothing left to do.
        env.env_seeds = None
    else:
        env.env_seeds = env.seed_manager.get_seeds(max_count=eval_num - eval_time)
    from src.eval_client import eval_env
    global_configs = importlib.import_module('env.global_configs')
    import isaaclab
    import curobo
    modules = {name: str(Path(module.__file__).resolve()) for name, module in
               [('eval_env', eval_env), ('global_configs', global_configs),
                ('isaaclab', isaaclab), ('curobo', curobo)]}
    if any(not Path(path).is_relative_to(Path(host['root'])) for path in modules.values()):
        raise RuntimeError(f'host imports escaped selected checkout: {modules}')
    from execution.artifacts import write_json
    write_json(Path(args_cli.codex_output) / 'host.json', dict(host, modules=modules))
    run_single(env, simulation_app)


if __name__ == '__main__':
    try:
        main()
    finally:
        simulation_app.close()
