"""Query saved measured depth; projection runs in perception.measured_depth."""
from functools import partial

from mcp import types

from .rendering import render_result

NAME = "read_depth"


def definition():
    return types.Tool(
        name=NAME,
        description="Read saved RGB-aligned measured optical-Z depth at 1..64 integer [u,v] pixels; returns metres and calibrated visible-surface XYZ. Never advances physics.",
        inputSchema=dict(
            type="object",
            properties=dict(
                observation_id=dict(type="integer", minimum=0),
                camera=dict(type="string", enum=["egoview"]),
                pixels_uv=dict(
                    type="array", minItems=1, maxItems=64,
                    items=dict(type="array", minItems=2, maxItems=2, items=dict(type="integer", minimum=0)),
                ),
            ),
            required=["observation_id", "camera", "pixels_uv"], additionalProperties=False,
        ),
        annotations=types.ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
        ),
    )


def call(client, arguments, metrics):
    return client.call(
        NAME, **arguments, metrics=metrics, defer_confirmation=True,
        render=partial(render_result, client, NAME, metrics=metrics),
    )
