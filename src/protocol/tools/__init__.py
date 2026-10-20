"""Enabled MCP tools in delivery order; each module owns its schema and adapter.

The server owns concurrency, cancellation, auditing and delivery confirmation.
Tool adapters run synchronously inside that shared transaction boundary.
"""
from control.profiles import control_profile
from . import act, finish, observe, read_depth, read_reference, status


def enabled_tools(reference=False, measured_depth=False):
    modules = [observe, act, status, finish]
    if measured_depth:
        modules.append(read_depth)
    if reference:
        modules.append(read_reference)
    return {module.NAME: module for module in modules}


def tool_definitions(reference=False, depth_estimation=True, profile=None, measured_depth=False):
    profile = profile or control_profile("robodojo")
    return [
        module.definition(profile, depth_estimation) if module is act else module.definition()
        for module in enabled_tools(reference, measured_depth).values()
    ]
