"""Execute bounded arm deltas; simulation-side validation lives in DeltaController."""
from functools import partial

from mcp import types

from .rendering import render_result

NAME = "act"


def vector_schema(size):
    return dict(type="array", items={"type": "number"}, minItems=size, maxItems=size)


ARM_ACTION_SCHEMA = dict(
    type="object",
    additionalProperties=False,
    required=["dpos", "max_steps"],
    properties={
        "dpos": dict(**vector_schema(3), description="TOTAL environment XYZ displacement in metres; norm <= 0.20."),
        "dquat": dict(
            anyOf=[vector_schema(4), {"type": "null"}],
            default=None,
            description="Relative environment-frame wxyz rotation; shortest angle <= pi/2. Null = identity.",
        ),
        "gripper": dict(
            type=["number", "null"],
            minimum=0,
            maximum=1,
            default=None,
            description="0 closes, 1 opens; null preserves the target.",
        ),
        "max_steps": dict(
            type="integer",
            minimum=1,
            maximum=100,
            description="Maximum synchronized native steps in which this arm remains active.",
        ),
    },
)


def action_schema(profile):
    from copy import deepcopy
    arms = {}
    for arm, settings in profile['arms'].items():
        schema = deepcopy(ARM_ACTION_SCHEMA)
        if settings['gripper'] == 'binary':
            schema['properties']['gripper'] = dict(enum=['open', 'close', None], default=None,
                                                   description='Open, close, or null to hold target.')
        elif settings['gripper'] == 'hand':
            del schema['properties']['gripper']
            schema['properties']['hand'] = dict(type='array', minItems=6, maxItems=6,
                items=dict(type='number', minimum=-3, maximum=3),
                description='Raw radian targets: ' + ', '.join(settings['hand_names']) + '; omit to hold.')
        elif settings['gripper'] == 'position_m':
            del schema['properties']['gripper']
            low, high = settings['gripper_position_limits_m']
            schema['properties']['gripper_position_m'] = dict(type='number', minimum=low, maximum=high,
                description='Absolute symmetric finger joint target in metres, not total jaw gap.')
            schema['required'].append('gripper_position_m')
        arms[arm] = schema
    return dict(type='object', additionalProperties=False, required=['arms'], properties={
        'arms': dict(type='object', additionalProperties=False, required=list(arms), properties=arms),
        'translation_step': dict(type='number', **profile['translation_step']),
        'rotation_step': dict(type='number', **profile['rotation_step']),
    })


def definition(profile, depth_estimation=True):
    properties = dict(
        observation_id=dict(type="integer", minimum=0),
        reason=dict(type="string", minLength=1, maxLength=4000),
        action=action_schema(profile),
    )
    required = list(properties)
    if depth_estimation:
        from perception.depth import DEPTH_SCHEMA
        properties["depth_estimates"] = DEPTH_SCHEMA
        required.append("depth_estimates")
    return types.Tool(
        name=NAME,
        description=(
            "Execute ONE bounded delta action (all configured arms required) "
            "using the latest inspected observation; "
            "return feedback and ALL enabled new RGB/tactile views and force readings. Never retry an uncertain action."
        ),
        inputSchema=dict(type="object", properties=properties, required=required, additionalProperties=False),
        annotations=types.ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False,
        ),
    )


def call(client, arguments, metrics):
    return client.call(
        NAME, **arguments, metrics=metrics, defer_confirmation=True,
        render=partial(render_result, client, NAME, metrics=metrics),
    )
