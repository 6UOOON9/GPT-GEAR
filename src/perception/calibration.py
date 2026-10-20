# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Episode-fixed camera calibration; dynamic poses use measured EE state only.

This is internal observation processing, not a Planner tool. Raw simulator camera
matrices may still be recorded privately, but are read here only at initialization.
"""
from copy import deepcopy

import numpy as np

CAMERA_AXES = '+X right, +Y up, -Z forward'
REFERENCES = frozenset({'environment', 'left_ee', 'right_ee', 'robot0_ee', 'head'})


def numeric_array(value, shape):
    """Reject text, booleans, nonfinite values and unexpected matrix shapes."""
    try:
        raw = np.asarray(value)
        if raw.shape != shape or raw.dtype.kind not in 'iuf':
            raise ValueError
        if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
            raise ValueError
        result = raw.astype(np.float64)
        if not np.isfinite(result).all():
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Invalid camera calibration numeric data') from None


def intrinsic_matrix(value):
    matrix = numeric_array(value, (3, 3))
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or not np.allclose(matrix[2], [0, 0, 1]):
        raise ValueError('Invalid camera pinhole calibration')
    return matrix


def rigid_matrix(value):
    matrix = numeric_array(value, (4, 4))
    rotation = matrix[:3, :3]
    if (not np.allclose(matrix[3], [0, 0, 0, 1])
            or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-4)
            or not np.isclose(np.linalg.det(rotation), 1, atol=1e-4)):
        raise ValueError('Invalid rigid camera calibration')
    return matrix


def ee_transform(pose):
    """Environment-from-observed-EE transform; pose uses position + wxyz."""
    try:
        pose = numeric_array(pose, (7,))
        q = pose[3:]
        scale = np.max(np.abs(q))
        if scale == 0:
            raise ValueError
        q = q / scale
        w, x, y, z = q / np.linalg.norm(q)
    except ValueError:
        raise ValueError('Camera calibration requires a valid current measured EE pose') from None
    result = np.eye(4)
    result[:3, :3] = [
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ]
    result[:3, 3] = pose[:3]
    return result


class EpisodeCalibration:
    """Freeze calibration once; no truth-based fallback or automatic recalibration."""
    def __init__(self):
        self._entries = None
        self._invalid = False

    @property
    def invalidated(self):
        return self._invalid

    def view_specs(self, observation):
        if self._invalid:
            raise ValueError('Camera calibration invalidated; start a new episode')
        try:
            return self._view_specs(observation)
        except (KeyError, TypeError, ValueError):
            self._invalid = True
            raise

    def _view_specs(self, observation):
        views = observation['views']
        if not isinstance(views, dict) or not views:
            raise ValueError('Camera calibration requires camera views')
        if self._entries is not None and set(views) != set(self._entries):
            raise ValueError('Camera calibration invalidated: camera set changed')
        entries, specs = {}, {}
        for name, view in views.items():
            reference = view.get('calibration_reference')
            if not isinstance(reference, str) or reference not in REFERENCES:
                raise ValueError('Camera calibration reference unavailable or unsupported; check benchmark adapter')
            signature = view.get('calibration_mount_signature')
            if not isinstance(signature, str) or not signature:
                raise ValueError('Camera mounting configuration unavailable; check benchmark adapter')
            rgb = np.asarray(view['rgb'])
            if rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) <= 0:
                raise ValueError('Camera calibration requires a valid RGB image')
            shape = list(rgb.shape[:2])
            current_ee = (None if reference == 'environment' else
                          ee_transform(observation['robot_state'].get(f'{reference}_pose')))
            if self._entries is None:
                intrinsic = intrinsic_matrix(view.get('intrinsic_K'))
                camera = rigid_matrix(view.get('camera_to_env_gl'))
                installation = camera if current_ee is None else np.linalg.inv(current_ee) @ camera
                entry = {'shape': shape, 'reference': reference, 'signature': signature,
                         'intrinsic': intrinsic.copy(), 'installation': installation.copy()}
            else:
                entry = self._entries[name]
                if (entry['shape'] != shape or entry['reference'] != reference
                        or entry['signature'] != signature):
                    raise ValueError('Camera calibration invalidated: image geometry or mounting changed')
            camera = (entry['installation'] if current_ee is None
                      else current_ee @ entry['installation'])
            specs[name] = {
                'shape': shape, 'pixel_order': 'row_col',
                'intrinsic_K': entry['intrinsic'].tolist(),
                'camera_to_env_gl': rigid_matrix(camera).tolist(),
                'coordinate_frame': 'environment', 'position_unit': 'm',
                'camera_axes': CAMERA_AXES, 'calibration_reference': reference,
                'extrinsic_source': ('fixed_calibration' if current_ee is None else 'ee_pose_composition'),
            }
            entries[name] = entry
        if self._entries is None:
            self._entries = deepcopy(entries)
        return specs
