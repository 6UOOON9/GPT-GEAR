"""Lazy benchmark registry; importing it never loads simulation libraries."""
from importlib import import_module

from environments import environment_package


def get_backend(name):
    module = import_module(environment_package(name) + '.backend')
    return module.Backend()
