"""Read episode status or its official result, without delivering images."""
from functools import partial

from mcp import types

from .rendering import render_result

NAME = "status"


def definition():
    return types.Tool(
        name=NAME,
        description="Read current status or the final official result, including after the environment closes. No images.",
        inputSchema=dict(type="object", properties={}, required=[], additionalProperties=False),
        annotations=types.ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
        ),
    )


def call(client, arguments, metrics):
    return client.call(
        NAME, **arguments, metrics=metrics, defer_confirmation=True,
        render=partial(render_result, client, NAME, metrics=metrics),
    )
