"""Key frames and phases inside a detected stroke."""

from __future__ import annotations

import numpy as np

from .geometry import clamp_index, joint, joint_angle
from .preprocess import Prepared
from .segment import StrokeWindow, swing_speed


def _argmin_in(x: np.ndarray, lo: int, hi: int, default: int) -> int:
    lo, hi = max(lo, 0), min(hi, len(x) - 1)
    if hi <= lo:
        return default
    seg = x[lo : hi + 1]
    if np.isnan(seg).all():
        return default
    return lo + int(np.nanargmin(seg))


def _argmax_in(x: np.ndarray, lo: int, hi: int, default: int) -> int:
    return _argmin_in(-x, lo, hi, default)


def key_frames(prep: Prepared, w: StrokeWindow, family: str) -> dict[str, int]:
    fps, n = prep.fps, prep.num_frames
    c = w.contact
    s = swing_speed(prep).astype(float)
    s[~prep.valid] = np.nan
    sec = lambda x: int(round(x * fps))  # noqa: E731

    if family == "overhead":
        # serve/smash contact is at full reach: the highest wrist point near the speed peak
        reach = joint(prep.p3, "r_wrist")[:, 1] - joint(prep.p3, "nose")[:, 1]
        c = _argmax_in(reach, c - sec(0.25), c + sec(0.1), c)

    finish = _argmin_in(s, c + sec(0.15), c + sec(0.9), clamp_index(c + sec(0.5), n))
    kf = {"start": w.start, "contact": c, "finish": finish, "end": w.end}

    if family == "overhead":
        toss_height = joint(prep.p3, "l_wrist")[:, 1] - joint(prep.p3, "nose")[:, 1]
        kf["trophy"] = _argmax_in(toss_height, c - sec(1.8), c - sec(0.15), clamp_index(c - sec(0.5), n))
        knee = np.fmin(
            joint_angle(prep.p3, "l_hip", "l_knee", "l_ankle"),
            joint_angle(prep.p3, "r_hip", "r_knee", "r_ankle"),
        )
        kf["load"] = _argmin_in(knee, c - sec(1.5), c - sec(0.05), clamp_index(c - sec(0.4), n))
        kf["start"] = min(kf["start"], kf["trophy"], kf["load"])
    else:
        # the wrist momentarily slows where the backswing turns into the forward swing
        kf["backswing_end"] = _argmin_in(s, c - sec(0.9), c - sec(0.1), clamp_index(c - sec(0.35), n))
    return kf


def phases(kf: dict[str, int], family: str, fps: float) -> list[dict]:
    t = lambda i: round(i / fps, 3)  # noqa: E731
    if family == "overhead":
        pivots = [("preparation", kf["start"], kf["trophy"]), ("acceleration", kf["trophy"], kf["contact"])]
    else:
        pivots = [
            ("preparation", kf["start"], kf["backswing_end"]),
            ("forward_swing", kf["backswing_end"], kf["contact"]),
        ]
    pivots.append(("follow_through", kf["contact"], kf["end"]))
    return [{"name": name, "start_s": t(a), "end_s": t(b)} for name, a, b in pivots if b > a]
