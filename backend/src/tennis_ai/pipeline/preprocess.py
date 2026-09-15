"""Cleaning, smoothing, normalization, handedness, and mirroring.

After ``prepare`` every downstream stage can assume a right-handed player:
left-handers are mirrored (x flipped, left/right joints swapped).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.signal import savgol_filter

from .skeleton import MIRROR, J, PoseSequence

Handedness = Literal["right", "left"]

# MediaPipe reports low visibility for motion-blurred joints whose positions are
# still usable (a swinging arm at contact), so only drop near-certain misses.
MIN_VISIBILITY = 0.05
MAX_GAP_S = 0.3


@dataclass
class Prepared:
    seq: PoseSequence          # original, unmirrored (used for the overlay)
    p3: np.ndarray             # (T, J, 3) smoothed world coords, canonical right-handed, NaN = missing
    p2: np.ndarray             # (T, J, 2) smoothed image coords in pixels, canonical, NaN = missing
    conf: np.ndarray           # (T, J) visibility (canonical joint order)
    valid: np.ndarray          # (T,) frame usable after gap filling
    torso3: float              # median torso length in metres
    torso2: float              # median torso length in pixels
    handedness: Handedness
    handedness_source: Literal["user", "detected", "default"]

    @property
    def fps(self) -> float:
        return self.seq.fps

    @property
    def num_frames(self) -> int:
        return self.seq.num_frames


def _fill_gaps(x: np.ndarray, max_gap: int) -> np.ndarray:
    """Linearly interpolate NaN runs of length <= max_gap along axis 0 (per column)."""
    out = x.copy()
    flat = out.reshape(out.shape[0], -1)
    t = np.arange(flat.shape[0])
    for c in range(flat.shape[1]):
        col = flat[:, c]
        good = ~np.isnan(col)
        if good.sum() < 2 or good.all():
            continue
        filled = np.interp(t, t[good], col[good])
        # only fill interior gaps that are short enough
        missing = ~good
        start = None
        for i in range(len(col) + 1):
            m = i < len(col) and missing[i]
            if m and start is None:
                start = i
            elif not m and start is not None:
                interior = start > 0 and i < len(col)
                if interior and (i - start) <= max_gap:
                    col[start:i] = filled[start:i]
                start = None
        flat[:, c] = col
    return out


def _smooth(x: np.ndarray, window: int) -> np.ndarray:
    """Savitzky–Golay smoothing over contiguous non-NaN segments."""
    if window < 5:
        return x
    out = x.copy()
    flat = out.reshape(out.shape[0], -1)
    ok_rows = ~np.isnan(flat).any(axis=1)
    i = 0
    n = len(ok_rows)
    while i < n:
        if not ok_rows[i]:
            i += 1
            continue
        j = i
        while j < n and ok_rows[j]:
            j += 1
        if j - i >= window:
            flat[i:j] = savgol_filter(flat[i:j], window, 2, axis=0)
        i = j
    return out


def _torso(points: np.ndarray) -> np.ndarray:
    sh = (points[:, J["l_shoulder"]] + points[:, J["r_shoulder"]]) / 2
    hp = (points[:, J["l_hip"]] + points[:, J["r_hip"]]) / 2
    return np.linalg.norm(sh - hp, axis=-1)


def wrist_speeds(p3: np.ndarray, fps: float, torso: float) -> np.ndarray:
    """(T, 2) speed of [left, right] wrist in torso lengths per second."""
    w = p3[:, [J["l_wrist"], J["r_wrist"]]]
    v = np.gradient(w, axis=0) * fps / max(torso, 1e-6)
    return np.linalg.norm(v, axis=-1)


def detect_handedness(p3: np.ndarray, fps: float, torso: float) -> tuple[Handedness, bool]:
    """Dominant hand = the wrist with the higher sustained peak speed. Returns (hand, confident)."""
    s = wrist_speeds(p3, fps, torso)
    if np.isnan(s).all(axis=0).any():
        return "right", False
    left, right = np.nanpercentile(s, 97, axis=0)
    if right >= left:
        return "right", right > 1.12 * left
    return "left", left > 1.12 * right


def mirror(p: np.ndarray, flip_x_about: float) -> np.ndarray:
    """Mirror horizontally (x -> flip_x_about - x) and swap left/right joints."""
    out = p[:, MIRROR].copy()
    out[..., 0] = flip_x_about - out[..., 0]
    return out


def prepare(seq: PoseSequence, handedness: str = "auto") -> Prepared:
    fps = seq.fps
    max_gap = max(1, int(MAX_GAP_S * fps))
    window = int(round(0.2 * fps)) | 1  # ~0.2 s, odd

    missing = (~seq.valid[:, None]) | (seq.conf < MIN_VISIBILITY)
    p3 = seq.kp3d.astype(np.float64).copy()
    p2 = (seq.kp2d * np.array([seq.width, seq.height])).astype(np.float64)
    p3[missing] = np.nan
    p2[missing] = np.nan
    p3 = _smooth(_fill_gaps(p3, max_gap), window)
    p2 = _smooth(_fill_gaps(p2, max_gap), window)

    core = [J["l_shoulder"], J["r_shoulder"], J["l_hip"], J["r_hip"]]
    valid = ~np.isnan(p3[:, core]).any(axis=(1, 2))

    t3 = _torso(p3)
    t2 = _torso(p2)
    torso3 = float(np.nanmedian(t3)) if valid.any() else 0.5
    torso2 = float(np.nanmedian(t2)) if valid.any() else seq.height / 4

    if handedness in ("right", "left"):
        hand, source = handedness, "user"
    else:
        hand, confident = detect_handedness(p3, fps, torso3)
        source = "detected" if confident else "default"
        if not confident:
            hand = "right"

    conf = seq.conf.copy()
    if hand == "left":
        p3 = mirror(p3, 0.0)
        p2 = mirror(p2, float(seq.width))
        conf = conf[:, MIRROR]

    return Prepared(
        seq=seq,
        p3=p3,
        p2=p2,
        conf=conf,
        valid=valid,
        torso3=torso3,
        torso2=torso2,
        handedness=hand,
        handedness_source=source,
    )
