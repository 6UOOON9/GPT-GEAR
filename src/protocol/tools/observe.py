"""Read a saved observation; image validation is shared with action results."""
from functools import partial

from mcp import types

from .rendering import render_result

NAME = "observe"


def definition():
    return types.Tool(
        name=NAME,
        description=(
            "Read a saved observation and ALL enabled RGB/tactile views and force readings, plus the act that directly produced it (if any). "
            "Omit observation_id for the latest record; specify it for history. Never captures a new frame. "
            "History is for comparison only; act requires the latest inspected observation. Live session only."
        ),
        inputSchema=dict(
            type="object",
            properties=dict(observation_id=dict(
                type="integer", minimum=0,
                description="Saved observation ID; omit for the latest record.",
            )),
            required=[], additionalProperties=False,
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
