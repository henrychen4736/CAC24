"""Build data-driven reference ranges from expert clips.

For every metric the default reference *rates* (informational metrics stay
informational), take the distribution over expert strokes and set
    good = [p15, p85], ok = [p3, p97]
keeping a bound open (null) wherever the default is open — e.g. "contact in
front" is only ever coached when it's too small.

Only trustworthy measurements are used:
  * values from a camera view the metric is unreliable from are excluded, and
    depth-dependent metrics (rotations, stance width, contact depth) are excluded
    from front/back views, where MediaPipe's depth noise would inflate the spread
    until the range stops ruling anything out (they keep their coaching defaults);
  * family-level ranges exclude stroke types that override that metric (a slice's
    low finish must not loosen the topspin backhand's range);
  * with ``shadow=True`` (swings without a ball, like THETIS), metrics that only
    mean something when striking a ball (leg drive) keep their coaching defaults.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..pipeline.classify import FAMILY_OF
from ..pipeline.feedback import load_references
from ..pipeline.metrics import METRICS, compute_metrics, estimate_view
from ..pipeline.phases import key_frames
from .dataset import prepared_clips


def _reliable(metric_id: str, view: str, shadow: bool = False) -> bool:
    defn = METRICS[metric_id]
    if view in defn.weak_views or (shadow and defn.ball_dependent):
        return False
    return not (defn.depth_sensitive and view in ("front", "back"))


def _range(values: np.ndarray, default: dict) -> dict:
    p3, p15, p85, p97 = np.percentile(values, [3, 15, 85, 97])
    good = [None if default["good"][0] is None else round(float(p15), 3),
            None if default["good"][1] is None else round(float(p85), 3)]
    ok = [None if default["ok"][0] is None else round(float(p3), 3),
          None if default["ok"][1] is None else round(float(p97), 3)]
    return {"good": good, "ok": ok}


def calibrate(
    pose_dir: Path,
    out: Path,
    skill: str = "expert",
    min_n: int = 12,
    view: str = "auto",
    shadow: bool = False,
) -> dict:
    """``view``: the dataset's camera position, or "auto" to use each clip's ``view``
    column and fall back to estimating it. Prefer the known value: a player who
    turns sideways during a swing makes a front-facing camera look "oblique".
    ``shadow``: the clips are swings without a ball (THETIS)."""
    defaults = load_references(None)
    by_family: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_type: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    clips = 0
    for row, prep, w in prepared_clips(pose_dir):
        if row.get("skill") != skill or row["stroke"] not in FAMILY_OF:
            continue
        stroke, family = row["stroke"], FAMILY_OF[row["stroke"]]
        clip_view = view if view != "auto" else (row.get("view") or estimate_view(prep)[0])
        values = compute_metrics(prep, key_frames(prep, w, family), family)
        clips += 1
        overridden = defaults.types.get(stroke, {})
        for mid, v in values.items():
            if v is None or not _reliable(mid, clip_view, shadow):
                continue
            by_type[stroke][mid].append(v)
            if mid not in overridden:
                by_family[family][mid].append(v)

    result: dict = {"families": {}, "types": {}, "stats": {}}
    for family, metrics in by_family.items():
        for mid, vals in metrics.items():
            entry, _ = defaults.lookup("", family, mid)
            arr = np.asarray(vals)
            result["stats"].setdefault(family, {})[mid] = {
                "n": len(arr), **{f"p{q}": round(float(np.percentile(arr, q)), 3)
                                  for q in (5, 25, 50, 75, 95)}}
            if entry is not None and len(arr) >= min_n:
                result["families"].setdefault(family, {})[mid] = _range(arr, entry)
    for stroke, metrics in by_type.items():
        for mid, vals in metrics.items():
            entry, _ = defaults.lookup(stroke, FAMILY_OF[stroke], mid)
            if entry is not None and len(vals) >= min_n and mid in defaults.types.get(stroke, {}):
                # only where the defaults distinguish this type from its family
                result["types"].setdefault(stroke, {})[mid] = _range(np.asarray(vals), entry)

    doc = {
        "version": 1,
        "source": "calibrated",
        "created": datetime.now(UTC).isoformat(),
        "dataset": str(pose_dir),
        "skill": skill,
        "view": view,
        "shadow": shadow,
        "clips": clips,
        **result,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2))
    n_ranges = sum(len(m) for m in result["families"].values()) + sum(
        len(m) for m in result["types"].values())
    print(f"Calibrated {n_ranges} ranges from {clips} {skill} clips -> {out}")
    return doc
