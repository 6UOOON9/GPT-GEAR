"""Atomic JSON artifacts, with explicit durability for control guards.

This module depends only on the standard library. Simulation callers supply
their own serializer for NumPy values.
"""
import json
import os
from pathlib import Path
import tempfile


def write_json(path, value, *, default=None, indent=2, durable=False):
    """Replace only after a complete write; retain the old file on write failure."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', prefix=f'.{path.name}.', suffix='.tmp',
            dir=path.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, default=default, ensure_ascii=False,
                      allow_nan=False, indent=indent)
            if indent is not None:
                stream.write('\n')
            stream.flush()
            if durable:
                os.fsync(stream.fileno())
        temporary.replace(path)
        if durable:
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_guard(path, value):
    """Persist both the guard contents and its directory entry before returning."""
    write_json(path, value, indent=None, durable=True)
