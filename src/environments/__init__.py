"""Locate environment packages without importing simulation dependencies."""
from environments.benchmarks import BENCHMARKS


def environment_package(benchmark):
    if benchmark not in BENCHMARKS:
        raise ValueError(f'unknown benchmark: {benchmark}')
    return 'environments.' + benchmark.replace('-', '_')
