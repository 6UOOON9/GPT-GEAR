"""LIBERO-plus initialization over the shared LIBERO control adapter."""
from ..libero_native import LiberoNativeBase


class LiberoNative(LiberoNativeBase):
    benchmark_name = 'libero-plus'
    warmup_steps = 10
