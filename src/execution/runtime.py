"""Shared process environment; no simulation imports."""
from pathlib import Path
import os
import re

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def thread_environment():
    """Normalize only invalid OpenMP counts for our child processes."""
    env = dict(os.environ)
    value = env.get('OMP_NUM_THREADS')
    if value is not None and not re.fullmatch(r'[1-9]\d*(?:\s*,\s*[1-9]\d*)*', value.strip()):
        env['OMP_NUM_THREADS'] = '1'
    return env
