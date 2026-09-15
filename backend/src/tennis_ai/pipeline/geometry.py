"""Vectorized geometry on (T, J, 3) joint arrays (y up, x–z horizontal)."""

from __future__ import annotations

import numpy as np

from .skeleton import J

UP = np.array([0.0, 1.0, 0.0])


def joint(p: np.ndarray, name: str) -> np.ndarray:
    return p[:, J[name]]


def midpoint(p: np.ndarray, a: str, b: str) -> np.ndarray:
    return (p[:, J[a]] + p[:, J[b]]) / 2


def angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle at ``b`` in degrees for arrays of points (..., 3)."""
    v1, v2 = a - b, c - b
    denom = np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1)
    cos = np.sum(v1 * v2, axis=-1) / np.where(denom > 1e-9, denom, np.nan)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def joint_angle(p: np.ndarray, a: str, b: str, c: str) -> np.ndarray:
    return angle(p[:, J[a]], p[:, J[b]], p[:, J[c]])


def horizontal(v: np.ndarray) -> np.ndarray:
    out = np.array(v, dtype=float, copy=True)
    out[..., 1] = 0.0
    return out


def yaw(v: np.ndarray) -> np.ndarray:
    """Direction of a vector in the horizontal plane, degrees."""
    return np.degrees(np.arctan2(v[..., 2], v[..., 0]))


def wrap_deg(d: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(d) + 180.0) % 360.0 - 180.0


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 1e-9, n, np.nan)


def angle_from_vertical(v: np.ndarray) -> np.ndarray:
    return angle(v, np.zeros_like(v), np.broadcast_to(UP, v.shape))


def finite(x) -> float | None:
    """Python float or None for NaN/inf (safe for JSON)."""
    if x is None:
        return None
    x = float(x)
    return x if np.isfinite(x) else None


def clamp_index(i: int, n: int) -> int:
    return int(min(max(i, 0), n - 1))
