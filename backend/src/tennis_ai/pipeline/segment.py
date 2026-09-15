"""Stroke detection from the hitting wrist's speed profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from .preprocess import Prepared, wrist_speeds
from .skeleton import J

MIN_PEAK_SPEED = 5.0      # torso lengths / s — below this it's a walk or a racket twirl, not a swing
RELATIVE_PEAK = 0.45      # a stroke must reach this fraction of the clip's fastest swings
MIN_GAP_S = 1.2           # closer peaks are one stroke (e.g. a high follow-through's second peak)
MAX_JITTER = 10.0         # wrist path / net sweep around a peak; above this it's a tracking glitch
WINDUP_S = 1.8            # a serve's windup (racket drop) is a fast motion that belongs to the serve
PRE_S = 1.2               # window before contact
POST_S = 0.8              # window after contact


@dataclass(frozen=True)
class StrokeWindow:
    start: int
    contact: int
    end: int
    peak_speed: float


def swing_speed(prep: Prepared) -> np.ndarray:
    """Hitting-wrist speed (canonical right wrist), torso lengths / s, NaN -> 0."""
    s = wrist_speeds(prep.p3, prep.fps, prep.torso3)[:, 1]
    return np.nan_to_num(s, nan=0.0)


def _is_glitch(prep: Prepared, peak: int) -> bool:
    """A left/right landmark swap makes the wrist jump back and forth: lots of path, no sweep."""
    fps = prep.fps
    a = max(0, peak - int(0.3 * fps))
    b = min(prep.num_frames - 1, peak + int(0.1 * fps))
    w = prep.p3[a : b + 1, J["r_wrist"]]
    path = np.nansum(np.linalg.norm(np.diff(w, axis=0), axis=1))
    sweep = np.linalg.norm(w[-1] - w[0])
    if not np.isfinite(sweep):
        return False
    return path / max(sweep, 0.3 * prep.torso3) > MAX_JITTER


def detect_strokes(
    prep: Prepared,
    accept: Callable[[StrokeWindow], bool] | None = None,
    overhead: Callable[[StrokeWindow], bool] | None = None,
) -> list[StrokeWindow]:
    """Swing-speed peaks → stroke windows.

    Every local maximum is a candidate. Plausibility checks (tracking glitches,
    and ``accept`` — e.g. "can this be the stroke the user said they filmed?")
    run *before* the minimum-gap suppression, so a rejected peak can never hide
    a real stroke right next to it. If ``overhead`` is given, a non-overhead
    peak shortly before an overhead one is that serve's windup, not a stroke.
    """
    fps = prep.fps
    s = swing_speed(prep)
    n = len(s)
    if n < int(0.5 * fps) or not prep.valid.any():
        return []
    ref = float(np.percentile(s[prep.valid], 99))
    threshold = max(MIN_PEAK_SPEED, RELATIVE_PEAK * ref)
    peaks, _ = find_peaks(
        s, height=threshold, distance=max(1, int(0.25 * fps)), prominence=0.4 * threshold
    )
    candidates: list[StrokeWindow] = []
    for p in peaks:
        start, end = max(0, p - int(PRE_S * fps)), min(n - 1, p + int(POST_S * fps))
        w = StrokeWindow(int(start), int(p), int(end), float(s[p]))
        if prep.valid[start : end + 1].mean() < 0.6 or _is_glitch(prep, w.contact):
            continue
        if accept is not None and not accept(w):
            continue
        candidates.append(w)

    if overhead is not None:
        serves = {w.contact for w in candidates if overhead(w)}
        windup = int(WINDUP_S * fps)
        candidates = [
            w for w in candidates
            if w.contact in serves or not any(0 < s - w.contact <= windup for s in serves)
        ]

    gap = int(MIN_GAP_S * fps)
    kept: list[StrokeWindow] = []
    for w in sorted(candidates, key=lambda w: w.peak_speed, reverse=True):
        if all(abs(w.contact - k.contact) >= gap for k in kept):
            kept.append(w)
    kept.sort(key=lambda w: w.contact)

    windows: list[StrokeWindow] = []
    for i, w in enumerate(kept):
        # a window must not reach back into the previous stroke's follow-through
        start = w.start if i == 0 else max(w.start, kept[i - 1].contact + int(0.3 * fps))
        windows.append(StrokeWindow(start, w.contact, w.end, w.peak_speed))
    return windows


def strongest_stroke(
    prep: Prepared, accept: Callable[[StrokeWindow], bool] | None = None
) -> StrokeWindow | None:
    """For single-stroke training clips: the fastest plausible swing.

    ``accept`` should encode the clip's known label (e.g. a serve clip may only
    pick a peak that can be a serve), otherwise a fast windup can win over the hit.
    Falls back to the raw fastest moment if nothing qualifies.
    """
    windows = detect_strokes(prep, accept)
    if windows:
        return max(windows, key=lambda w: w.peak_speed)
    s = swing_speed(prep)
    if not prep.valid.any():
        return None
    p = int(np.argmax(np.where(prep.valid, s, 0.0)))
    fps, n = prep.fps, len(s)
    return StrokeWindow(max(0, p - int(PRE_S * fps)), p, min(n - 1, p + int(POST_S * fps)), float(s[p]))
