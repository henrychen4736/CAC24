"""Fixed-size stroke features shared by training and inference.

A stroke becomes a (T_OUT, NUM_FEATURES) array sampled on a fixed time grid
around contact. Positions are hip-centred, scaled by torso length, and rotated
about the vertical axis so the hip line at contact points along +x. That makes
the features independent of where the camera stood.

Before resampling, every clip is low-passed with the same smoothing in *seconds*
(BANDWIDTH_S). Training clips (THETIS, 17–19 fps) and phone videos (30–60 fps)
then carry the same temporal detail, so velocities mean the same thing at
training and inference time.

Layout per time step:
    [0:39)   positions of 13 joints (x, y, z)
    [39:78)  velocities of the same joints (torso lengths / s, x0.1)
    [78:86)  joint angles / 180: elbows, shoulders, knees, hips (L, R each)
    [86:88)  sin, cos of hip–shoulder separation
    [88]     1 if the frame had a usable pose, else 0
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from ..pipeline.geometry import angle, horizontal, wrap_deg, yaw
from ..pipeline.preprocess import Prepared
from ..pipeline.skeleton import J

FEATURE_VERSION = 2
WINDOW_S = (-1.0, 0.6)
T_OUT = 48
BANDWIDTH_S = 0.05  # Gaussian sigma applied along time before resampling

FEATURE_JOINTS = (
    "nose", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
    "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle",
)
_IDX = [J[j] for j in FEATURE_JOINTS]
_NJ = len(FEATURE_JOINTS)
POS = slice(0, 3 * _NJ)
VEL = slice(3 * _NJ, 6 * _NJ)
NUM_FEATURES = 6 * _NJ + 8 + 2 + 1

_ANGLES = (
    ("l_shoulder", "l_elbow", "l_wrist"), ("r_shoulder", "r_elbow", "r_wrist"),
    ("l_hip", "l_shoulder", "l_elbow"), ("r_hip", "r_shoulder", "r_elbow"),
    ("l_hip", "l_knee", "l_ankle"), ("r_hip", "r_knee", "r_ankle"),
    ("l_shoulder", "l_hip", "l_knee"), ("r_shoulder", "r_hip", "r_knee"),
)


def _rotate_y(p: np.ndarray, theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    x, z = p[..., 0], p[..., 2]
    out = p.copy()
    out[..., 0] = c * x + s * z
    out[..., 2] = -s * x + c * z
    return out


def _lowpass(p: np.ndarray, sigma_frames: float) -> np.ndarray:
    """Gaussian smoothing along time that ignores gaps (normalized convolution)."""
    if sigma_frames < 0.3:
        return p
    ok = np.isfinite(p)
    num = gaussian_filter1d(np.where(ok, p, 0.0), sigma_frames, axis=0, mode="nearest")
    den = gaussian_filter1d(ok.astype(float), sigma_frames, axis=0, mode="nearest")
    out = num / np.where(den > 1e-6, den, np.nan)
    out[~ok] = np.nan  # gaps stay gaps
    return out


def _sample(p: np.ndarray, frame_pos: np.ndarray) -> np.ndarray:
    """Linear interpolation along axis 0 at fractional frame positions (NaN outside)."""
    n = p.shape[0]
    i0 = np.floor(frame_pos).astype(int)
    frac = (frame_pos - i0)[:, None, None]
    inside = (i0 >= 0) & (i0 + 1 < n)
    i0c = np.clip(i0, 0, n - 1)
    i1c = np.clip(i0 + 1, 0, n - 1)
    out = (1 - frac) * p[i0c] + frac * p[i1c]
    out[~inside] = np.nan
    return out


def stroke_features(prep: Prepared, contact: int) -> np.ndarray:
    fps = prep.fps
    rel = np.linspace(WINDOW_S[0], WINDOW_S[1], T_OUT)
    frames = contact + rel * fps

    p = prep.p3
    hip_c = (p[:, J["l_hip"]] + p[:, J["r_hip"]]) / 2
    rel_p = (p - hip_c[:, None]) / prep.torso3
    hip_axis = horizontal(p[contact, J["r_hip"]] - p[contact, J["l_hip"]])
    theta = float(np.arctan2(hip_axis[2], hip_axis[0])) if np.isfinite(hip_axis).all() else 0.0
    rel_p = _rotate_y(rel_p, theta)  # hip line at contact -> +x
    rel_p = _lowpass(rel_p, BANDWIDTH_S * fps)

    s = _sample(rel_p, frames)                       # (T_OUT, J, 3)
    pos = s[:, _IDX]
    dt = (WINDOW_S[1] - WINDOW_S[0]) / (T_OUT - 1)
    vel = np.gradient(pos, dt, axis=0) * 0.1

    angs = np.stack([angle(s[:, J[a]], s[:, J[b]], s[:, J[c]]) for a, b, c in _ANGLES], -1) / 180
    sep = np.radians(wrap_deg(
        yaw(s[:, J["r_shoulder"]] - s[:, J["l_shoulder"]]) - yaw(s[:, J["r_hip"]] - s[:, J["l_hip"]])
    ))
    valid = np.isfinite(pos).all(axis=(1, 2)).astype(float)

    x = np.concatenate(
        [pos.reshape(T_OUT, -1), vel.reshape(T_OUT, -1), angs,
         np.sin(sep)[:, None], np.cos(sep)[:, None], valid[:, None]],
        axis=1,
    )
    return np.nan_to_num(x, nan=0.0).astype(np.float32)


def rotate_features(x: np.ndarray, theta: float) -> np.ndarray:
    """Augmentation: rotate position/velocity triplets about the vertical axis.

    Works on (..., T_OUT, NUM_FEATURES) arrays; angles and separation are
    rotation-invariant and left untouched.
    """
    out = x.copy()
    for sl in (POS, VEL):
        block = out[..., sl].reshape(*out.shape[:-1], _NJ, 3)
        out[..., sl] = _rotate_y(block, theta).reshape(*out.shape[:-1], 3 * _NJ)
    return out
