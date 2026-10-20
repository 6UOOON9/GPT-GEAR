"""S2 declarations only: never queries ground truth, depth sensors or backprojection."""

import argparse
import math


def boolean_string(value):
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("expected exactly true or false")


DEPTH_SCHEMA = dict(
    type="array",
    minItems=1,
    items=dict(
        type="object",
        additionalProperties=False,
        required=["object", "camera", "pixel_uv", "depth_m"],
        properties=dict(
            object=dict(type="string", minLength=1, description="Visual object label"),
            camera=dict(type="string", description="Camera name in the current observation"),
            pixel_uv=dict(
                type="array",
                items=dict(type="number"),
                minItems=2,
                maxItems=2,
                description="Visible object centre [u,v] = [column,row]",
            ),
            depth_m=dict(
                type="number",
                exclusiveMinimum=0,
                description="Estimated positive optical-axis Z depth in metres; not range",
            ),
        ),
    ),
)


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_estimates(estimates, observation):
    if not isinstance(estimates, list) or not estimates:
        raise ValueError("S2 requires nonempty top-level depth_estimates before every act")
    for estimate in estimates:
        if not isinstance(estimate, dict) or set(estimate) != {"object", "camera", "pixel_uv", "depth_m"}:
            raise ValueError("depth estimate requires exactly object, camera, pixel_uv, depth_m")
        if not isinstance(estimate["object"], str) or not estimate["object"].strip():
            raise ValueError("depth estimate object must be a nonempty visual label")
        camera = estimate["camera"]
        if (
            not isinstance(camera, str)
            or camera not in observation["images"]
            or camera not in observation["view_specs"]
        ):
            raise ValueError("depth estimate camera must name a current RGB view")
        pixel = estimate["pixel_uv"]
        if not isinstance(pixel, list) or len(pixel) != 2 or not all(finite(x) for x in pixel):
            raise ValueError("pixel_uv must contain two finite numbers [u,v]")
        height, width = observation["view_specs"][camera]["shape"]
        if not (0 <= pixel[0] < width and 0 <= pixel[1] < height):
            raise ValueError("depth estimate pixel is outside the current image")
        if not finite(estimate["depth_m"]) or estimate["depth_m"] <= 0:
            raise ValueError("depth_m must be a positive finite optical-axis Z estimate")
