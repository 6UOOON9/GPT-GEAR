"""Policy-facing observation contracts; importable without simulation dependencies."""
import math
from environments.benchmarks import TACTILE_MODES
from control.profiles import control_profile

TACTILE_NAMES = ('left_tactile', 'right_tactile')


def observation_profile(benchmark, tactile_mode=None, measured_depth=None):
    measured_depth = benchmark == 'robocasa-gr1' if measured_depth is None else measured_depth
    if type(measured_depth) is not bool or (measured_depth and benchmark != 'robocasa-gr1'):
        raise ValueError('measured depth requires robocasa-gr1')
    result = dict(rgb_cameras=control_profile(benchmark)['cameras'], measured_depth=measured_depth)
    if benchmark != 'univtac':
        if tactile_mode is not None:
            raise ValueError('tactile options require univtac')
        return result
    mode = 'force' if tactile_mode is None else tactile_mode
    if mode not in TACTILE_MODES:
        raise ValueError('invalid UniVTAC tactile mode')
    result.update(tactile_mode=mode,
                  tactile_images=list(TACTILE_NAMES) if mode in ('image', 'image-force') else [],
                  contact_forces=list(TACTILE_NAMES) if mode in ('force', 'image-force') else [])
    return result


def validate_force(value):
    keys = {'force_N', 'magnitude_N', 'coordinate_frame', 'unit', 'measurement'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('invalid contact force fields')
    vector = value['force_N']
    if (not isinstance(vector, list) or len(vector) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)
            or type(value['magnitude_N']) not in (int, float)
            or not math.isfinite(value['magnitude_N'])
            or not math.isclose(math.hypot(*vector), value['magnitude_N'], rel_tol=1e-6, abs_tol=1e-9)
            or value['coordinate_frame'] != 'robot_base' or value['unit'] != 'N'
            or value['measurement'] != 'net_contact_force_on_gelpad'):
        raise ValueError('invalid native contact force units, frame or values')
    return value


def validate_observation(observation, profile):
    """Check the complete public image/force boundary, including saved history."""
    rgb = set(observation.get('view_specs', {}))
    expected_rgb = profile['rgb_cameras']
    if not rgb or (expected_rgb is not None and rgb != set(expected_rgb)):
        raise ValueError('incorrect RGB camera set')
    tactile = set(profile.get('tactile_images', []))
    forces = set(profile.get('contact_forces', []))
    if set(observation.get('images', {})) != rgb | tactile:
        raise ValueError('image modality boundary violation')
    if tactile:
        specs = observation.get('tactile_specs', {})
        if set(specs) != tactile:
            raise ValueError('missing tactile image specifications')
        for spec in specs.values():
            if (set(spec) != {'shape', 'signal'} or spec['signal'] != 'native_tactile_rgb'
                    or not isinstance(spec['shape'], list) or len(spec['shape']) != 2
                    or any(type(n) is not int or n <= 0 for n in spec['shape'])):
                raise ValueError('invalid tactile image specification')
    elif 'tactile_specs' in observation:
        raise ValueError('disabled tactile images present')
    if forces:
        readings = observation.get('contact_forces', {})
        if set(readings) != forces:
            raise ValueError('missing native contact forces')
        for reading in readings.values():
            validate_force(reading)
    elif 'contact_forces' in observation:
        raise ValueError('disabled contact forces present')
    if 'tactile_mode' in profile and observation.get('tactile_mode') != profile['tactile_mode']:
        raise ValueError('observation tactile mode mismatch')
    if 'tactile_mode' not in profile and 'tactile_mode' in observation:
        raise ValueError('tactile options require univtac')
    if profile['measured_depth']:
        if set(observation.get('depth_views', {})) != rgb:
            raise ValueError('missing measured depth views')
        for name, spec in observation['depth_views'].items():
            if (spec.get('shape') != observation['view_specs'][name]['shape'] or spec.get('unit') != 'm'
                    or spec.get('access_tool') != 'read_depth'):
                raise ValueError('invalid measured depth metadata')
    elif 'depth_views' in observation:
        raise ValueError('disabled measured depth present')
    return dict(observation['view_specs'], **observation.get('tactile_specs', {}))
