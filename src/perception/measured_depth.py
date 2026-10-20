"""Saved RGB-aligned depth access adapted from astra-as-policy (see NOTICE)."""
import hashlib
import numpy as np

def read_depth(self, observation_id, camera, pixels_uv):
    """Read saved sensor pixels only; never advances physics or queries object truth."""
    if not self.measured_depth:
        raise ValueError('measured depth is disabled')
    if type(observation_id) is not int or observation_id < 0:
        raise ValueError('observation_id must be a nonnegative integer')
    observation = self.read_observation(observation_id)['observation']
    if camera != 'egoview' or camera not in observation.get('depth_views', {}):
        raise ValueError('unknown depth camera')
    if not isinstance(pixels_uv, list) or not 1 <= len(pixels_uv) <= 64:
        raise ValueError('pixels_uv requires 1..64 integer [u,v] pairs')
    height, width = observation['depth_views'][camera]['shape']
    for pixel in pixels_uv:
        if (not isinstance(pixel, list) or len(pixel) != 2
                or any(type(x) is not int for x in pixel)
                or not 0 <= pixel[0] < width or not 0 <= pixel[1] < height):
            raise ValueError('depth pixel must be an in-bounds integer [u,v] pair')
    directory = self.output / 'observations' / f'{observation_id:06d}'
    path = directory / 'depth_0.npy'
    if path.resolve() != path or hashlib.sha256(path.read_bytes()).hexdigest() != observation['depth_views'][camera]['sha256']:
        raise ValueError('saved depth changed')
    depth = np.load(path, allow_pickle=False)
    if depth.dtype != np.float32 or depth.shape != (height, width) or not np.isfinite(depth).all() or np.any(depth <= 0):
        raise ValueError('invalid saved depth')
    spec = observation['view_specs'][camera]
    inverse_k = np.linalg.inv(np.asarray(spec['intrinsic_K'], dtype=float))
    transform = np.asarray(spec['camera_to_env_gl'], dtype=float)
    samples = []
    for u, v in pixels_uv:
        z = float(depth[v, u])
        xyz_cv = z * (inverse_k @ np.array([u, v, 1.]))
        xyz_env = transform @ np.r_[xyz_cv * [1., -1., -1.], 1.]
        samples.append(dict(pixel_uv=[u, v], depth_m=z, point_env_m=xyz_env[:3].tolist()))
    result = dict(ok=True, episode_id=self.episode_id, observation_id=observation_id,
        latest_observation_id=self.version, is_latest=observation_id == self.version,
        camera=camera, samples=samples,
        convention='Measured positive optical-axis Z. point_env_m is the visible surface pixel backprojected with this observation calibration; not an object centre.')
    self.record(dict(event='depth_query', observation_id=observation_id, camera=camera, samples=samples))
    return result
