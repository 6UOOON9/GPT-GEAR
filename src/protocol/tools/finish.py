"""End control; official task success is decided by the simulation environment."""
from functools import partial

from mcp import types

from .rendering import render_result

NAME = "finish"


def definition():
    return types.Tool(
        name=NAME,
        description="End this episode, not declare success. Requires the latest observation; prohibited after uncertain motion.",
        inputSchema=dict(
            type="object",
            properties=dict(
                observation_id=dict(type="integer", minimum=0),
                reason=dict(type="string", minLength=1, maxLength=4000),
            ),
            required=["observation_id", "reason"], additionalProperties=False,
        ),
        annotations=types.ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False,
        ),
    )


def call(client, arguments, metrics):
    return client.call(
        NAME, **arguments, metrics=metrics, defer_confirmation=True,
        render=partial(render_result, client, NAME, metrics=metrics),
    )
