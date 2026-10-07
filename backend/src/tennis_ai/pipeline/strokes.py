"""Stroke types and families, and pose cues that check a swing can be the stroke the user filmed.

The stroke type comes from the user; nothing here guesses it. The cues only
filter out motions in the clip that can't be that stroke (ball bounces before a
serve, a serve's windup, ready-position fidgets).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import joint
from .preprocess import Prepared
from .segment import StrokeWindow

FAMILY_OF: dict[str, str] = {
    "forehand": "forehand",
    "forehand_slice": "forehand",
    "forehand_volley": "forehand",
    "backhand_1h": "backhand",
    "backhand_2h": "backhand",
    "backhand_slice": "backhand",
    "backhand_volley": "backhand",
    "serve": "overhead",
    "smash": "overhead",
}
STROKE_TYPES: tuple[str, ...] = tuple(FAMILY_OF)


@dataclass(frozen=True)
class HeuristicCues:
    wrist_above_head: float   # torso lengths, highest point just around contact
    toss_arm_up: float        # non-hitting wrist above head before contact, torso lengths
    racket_up_early: float    # hitting wrist vs shoulder just before contact, torso lengths


def _nan(fn, x) -> float:
    x = np.asarray(x, dtype=float)
    return float(fn(x[np.isfinite(x)])) if np.isfinite(x).any() else float("nan")


def heuristic_cues(prep: Prepared, w: StrokeWindow) -> HeuristicCues:
    p, fps, t3 = prep.p3, prep.fps, prep.torso3
    c = w.contact
    sl = lambda a, b: slice(max(0, c + int(a * fps)), max(1, c + int(b * fps) + 1))  # noqa: E731
    nose_y = joint(p, "nose")[:, 1]

    around = sl(-0.25, 0.1)  # peak wrist speed can trail the real (highest) contact a little
    above = _nan(np.max, joint(p, "r_wrist")[around, 1] - nose_y[around]) / t3
    toss = sl(-1.5, -0.2)
    toss_up = _nan(np.max, joint(p, "l_wrist")[toss, 1] - nose_y[toss]) / t3
    # serves arrive at contact from the trophy / racket drop (wrist already high);
    # a one-handed backhand's high finish arrives from below the waist
    pre = sl(-0.35, -0.1)
    early = _nan(np.median, joint(p, "r_wrist")[pre, 1] - joint(p, "r_shoulder")[pre, 1]) / t3
    return HeuristicCues(above, toss_up, early)


def _overhead_score(cues: HeuristicCues) -> float:
    """> 0 means overhead: high contact AND tossing arm went up AND racket was already high."""
    return min(
        np.nan_to_num(cues.wrist_above_head, nan=-1) - 0.1,
        np.nan_to_num(cues.toss_arm_up, nan=-1) - 0.15,
        np.nan_to_num(cues.racket_up_early, nan=-1) + 0.3,
    )


def is_overhead(cues: HeuristicCues) -> bool:
    return _overhead_score(cues) > 0


def fits_family(cues: HeuristicCues, family: str) -> bool:
    """Drop detections that can't be a stroke of the family the user filmed.

    A serve contact is never well below the head; a groundstroke is never a
    clear overhead. This removes ball bounces and ready-position fidgets from
    serve videos without second-guessing plausible strokes.
    """
    if family == "overhead":
        return not (cues.wrist_above_head < -0.2)
    return not (_overhead_score(cues) > 0.2)
