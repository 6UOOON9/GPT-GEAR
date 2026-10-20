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

# Adapted from RPent robots/robodojo/delta.py.
"""Environment-frame delta contract and numpy-only SO(3) helpers (wxyz)."""
from __future__ import annotations

import numbers
import numpy as np

MAX_TRANSLATION = 0.20
MAX_ROTATION = np.pi / 2
MIN_TRANSLATION_STEP = 0.001
MAX_TRANSLATION_STEP = 0.02
MIN_ROTATION_STEP = 0.005
MAX_ROTATION_STEP = 0.10
POSITION_TOLERANCE = 0.002
ROTATION_TOLERANCE = 0.01
MAX_STEPS = 100


def scalar(value, name, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')
    if not np.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')
    return float(value)


def vector(value, name, limit):
    raw = np.asarray(value)
    if (raw.shape != (3,) or raw.dtype.kind not in 'iuf'
            or any(isinstance(item, (bool, np.bool_)) for item in value)):
        raise ValueError(f'{name} must contain three finite numbers')
    result = raw.astype(float)
    if not np.isfinite(result).all() or np.linalg.norm(result) > limit:
        raise ValueError(f'{name} norm must be finite and <= {limit}')
    return result


def quaternion(value, name, max_angle):
    """Validate/normalize a relative wxyz quaternion and bound its shortest angle."""
    raw = np.asarray(value)
    if (raw.shape != (4,) or raw.dtype.kind not in 'iuf'
            or any(isinstance(item, (bool, np.bool_)) for item in value)):
        raise ValueError(f'{name} must contain four finite numbers (wxyz)')
    q = raw.astype(float)
    if not np.isfinite(q).all() or not np.any(q):
        raise ValueError(f'{name} must be a nonzero finite wxyz quaternion')
    # Scale first: finite nonunit inputs must not overflow/underflow their norm.
    q /= np.max(np.abs(q))
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q = -q
    angle = 2 * np.arctan2(np.linalg.norm(q[1:]), q[0])
    if angle > max_angle + 1e-12:
        raise ValueError(f'{name} shortest rotation angle must be <= {max_angle} radians')
    return q


def normalize_quat(value):
    q = np.asarray(value, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all():
        raise ValueError('invalid measured wxyz quaternion')
    norm = np.linalg.norm(q)
    if not np.isfinite(norm) or norm < 1e-12:
        raise ValueError('invalid measured wxyz quaternion')
    return q / norm


def multiply(a, b):
    return normalize_quat(np.r_[a[0]*b[0] - np.dot(a[1:], b[1:]),
                                a[0]*b[1:] + b[0]*a[1:] + np.cross(a[1:], b[1:])])


def exp_quat(rotvec):
    angle = np.linalg.norm(rotvec)
    # sinc avoids division by zero and preserves very small rotations.
    return normalize_quat(np.r_[np.cos(angle/2), rotvec * (0.5*np.sinc(angle/(2*np.pi)))])


def rotation_error(goal, current):
    """Log(R_goal @ R_current.T), shortest rotation in environment axes."""
    q = multiply(goal, current * np.array([1., -1., -1., -1.]))
    if q[0] < 0:
        q = -q
    sine = np.linalg.norm(q[1:])
    if sine < 1e-12:
        return 2*q[1:]
    return q[1:] * (2*np.arctan2(sine, q[0])/sine)


def limit_norm(value, maximum):
    norm = np.linalg.norm(value)
    return value * min(1., maximum/norm) if norm else value.copy()

