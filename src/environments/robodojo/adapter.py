"""Adapt the supported original factory without rewriting host sources."""
from contextlib import contextmanager
from pathlib import Path
from types import MethodType
import re


class NoPolicyClient:
    def __init__(self, **kwargs):
        pass

    def call(self, *, func_name, **kwargs):
        if func_name != 'reset':
            raise RuntimeError(f'unexpected native policy request: {func_name}')
        return None

    def close(self):
        pass


def seed_manager_class(base, assets, benchmark):
    class SelectedLayoutSeedManager(base):
        def init_eval(self, completed_layout_ids=None, abandoned_layout_ids=None):
            self.eval_seed = self.config.get('seed', 0)
            directory = Path(assets) / 'Eval_Layout' / benchmark / self.config_name / str(self.eval_seed)
            pattern = re.compile(rf'{re.escape(self.task_name)}_(\d+)\.json')
            self.seed_info = {}
            for path in directory.iterdir():
                match = pattern.fullmatch(path.name)
                if match:
                    self.seed_info[int(match[1])] = {'scene_layout': str(path)}
            requested = self.config.get('layout_id')
            ids = sorted(self.seed_info)
            if requested is not None:
                if type(requested) is not int or requested < 0 or requested not in self.seed_info:
                    raise ValueError(f'layout {requested!r} does not exist for {self.task_name}')
                ids = [requested]
            excluded = set(completed_layout_ids or ()) | set(abandoned_layout_ids or ())
            self.seed_list = [i for i in ids if i not in excluded]
            self.st_idx = self.idx = 0
            self.ed_idx = len(self.seed_list)
            self.type = 'eval'
            self._current_batch_seeds = None
    return SelectedLayoutSeedManager


@contextmanager
def factory_bindings(module, seed_class):
    original_client, original_seed = module.WsModelClient, module.SeedManager
    module.WsModelClient, module.SeedManager = NoPolicyClient, seed_class
    try:
        yield
    finally:
        module.WsModelClient, module.SeedManager = original_client, original_seed


def control_episode(self):
    from environments.robodojo.native import NativeEnvironment
    from execution.session import Session
    self.codex_control = Session(
        NativeEnvironment(self), self.deploy_cfg['codex_output'],
        port=int(self.deploy_cfg['port']),
        depth_estimation=self.deploy_cfg['codex_depth_estimation'],
        reference_manifest_sha256=self.deploy_cfg['codex_reference_manifest_sha256'],
        **{key: float(self.deploy_cfg['codex_' + key])
           for key in ('connect_timeout', 'idle_timeout', 'request_timeout')})
    self.codex_control.run()


def create_eval_env(config, app, resume_state=None):
    from env.global_configs import ASSETS_PATH, BENCHMARK
    from src.eval_client import eval_env
    if resume_state is not None:
        raise ValueError('active Codex episodes cannot be resumed')
    selected = seed_manager_class(eval_env.SeedManager, ASSETS_PATH, BENCHMARK)
    with factory_bindings(eval_env, selected):
        instance = eval_env.create_eval_env(config, app, resume_state=None)
    instance.codex_control = None
    instance.eval_one_episode = MethodType(control_episode, instance)
    return instance
