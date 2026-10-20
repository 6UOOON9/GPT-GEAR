"""Shared, stdlib-only capability handshake (no legacy-default guessing)."""

from control.profiles import control_profile, validate_profile
from protocol.feedback import FEEDBACK_FORMAT_VERSION

CAPABILITY_VERSION = "sim-control-v2"


def capabilities(depth_estimation, reference_manifest_sha256=None, benchmark="robodojo", tactile_mode=None, measured_depth=None):
    result = dict(
        capability_version=CAPABILITY_VERSION,
        benchmark=benchmark, control_profile=control_profile(benchmark),
        feedback_format_version=FEEDBACK_FORMAT_VERSION,
        depth_estimation=depth_estimation,
        reference_enabled=reference_manifest_sha256 is not None,
        reference_manifest_sha256=reference_manifest_sha256,
    )
    from perception.modalities import observation_profile
    result["observation_profile"] = observation_profile(benchmark, tactile_mode, measured_depth)
    result['measured_depth'] = result['observation_profile']['measured_depth']
    validate_capabilities(result)
    return result


def validate_capabilities(value):
    if (
        value.get("capability_version") != CAPABILITY_VERSION
        or value.get("feedback_format_version") != FEEDBACK_FORMAT_VERSION
        or type(value.get("depth_estimation")) is not bool
        or type(value.get("reference_enabled")) is not bool
        or "reference_manifest_sha256" not in value
    ):
        raise ValueError("missing or incompatible control capabilities")
    validate_profile(value.get("control_profile"), value.get("benchmark"))
    from perception.modalities import observation_profile
    observed = value.get('observation_profile')
    if not isinstance(observed, dict) or observed != observation_profile(
            value['benchmark'], observed.get('tactile_mode'), observed.get('measured_depth')):
        raise ValueError('incompatible observation profile')
    if (type(value.get('measured_depth')) is not bool or value['measured_depth'] != observed['measured_depth']
            or (value['measured_depth'] and value['depth_estimation'])):
        raise ValueError('incompatible measured depth and estimation capabilities')
    digest = value["reference_manifest_sha256"]
    if value["reference_enabled"]:
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid reference manifest digest")
    elif digest is not None:
        raise ValueError("disabled reference must not have a manifest digest")
