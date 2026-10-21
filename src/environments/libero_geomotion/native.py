"""Reuse LIBERO control; preserve GeoMotion's exact fixed-state reset."""
from ..libero_native import LiberoNativeBase


class GeoMotionNative(LiberoNativeBase):
    benchmark_name = 'libero-geomotion'
    warmup_steps = 0
    environment_options = dict(hard_reset=False, robots=['Panda'])

    def reset_environment(self, initial):
        self.env.env.reset()
        self.obs = self.env.set_init_state(initial)

    def __init__(self, args):
        super().__init__(args)
        self.identity.update(args.geomotion_identity)
