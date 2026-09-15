"""Rate metrics against reference ranges and turn them into priorities."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np

from ..schemas import Metric, Priority, Reference, Stroke, Summary
from .metrics import METRICS, MetricDef

_CONF_ORDER = ["low", "medium", "high"]


@dataclass
class ReferenceSet:
    families: dict[str, dict[str, dict | None]]
    types: dict[str, dict[str, dict | None]]
    source: str

    def lookup(self, stroke_type: str, family: str, metric_id: str) -> tuple[dict | None, str]:
        """Returns (range or None for info-only, source)."""
        per_type = self.types.get(stroke_type, {})
        if metric_id in per_type:
            entry = per_type[metric_id]
        else:
            entry = self.families.get(family, {}).get(metric_id)
        if entry is None:
            return None, self.source
        return entry, entry.get("source", self.source)


def load_references(calibrated: Path | None = None) -> ReferenceSet:
    text = resources.files("tennis_ai.data").joinpath("reference_default.json").read_text()
    base = json.loads(text)
    ref = ReferenceSet(base["families"], base.get("types", {}), "default")
    if calibrated and calibrated.exists():
        cal = json.loads(calibrated.read_text())
        for fam, metrics in cal.get("families", {}).items():
            for mid, rng in metrics.items():
                # calibration only overrides metrics the defaults rate (or explicitly marks)
                ref.families.setdefault(fam, {})[mid] = rng | {"source": "calibrated"} if rng else None
        for typ, metrics in cal.get("types", {}).items():
            for mid, rng in metrics.items():
                ref.types.setdefault(typ, {})[mid] = rng | {"source": "calibrated"} if rng else None
        ref.source = "calibrated"
    return ref


def _lo(b):
    return -np.inf if b is None else float(b)


def _hi(b):
    return np.inf if b is None else float(b)


def rate(value: float, good: list, ok: list) -> tuple[str, int, str | None]:
    """Returns (rating, score 0-100, direction 'low'/'high' when out of the good band)."""
    g_lo, g_hi, o_lo, o_hi = _lo(good[0]), _hi(good[1]), _lo(ok[0]), _hi(ok[1])
    if g_lo <= value <= g_hi:
        return "good", 100, None
    low = value < g_lo
    edge, outer = (g_lo, o_lo) if low else (g_hi, o_hi)
    band = abs(edge - outer) if np.isfinite(outer) else max(abs(edge) * 0.25, 1e-3)
    dist = abs(value - edge)
    direction = "low" if low else "high"
    if dist <= band:
        return "fair", int(round(100 - 40 * dist / band)), direction
    beyond = dist - band
    return "needs_work", int(round(max(0.0, 60 - 60 * beyond / band))), direction


def _confidence(defn: MetricDef, view: str, visibility: float) -> str:
    level = 2
    if defn.depth_sensitive or defn.camera_sensitive:
        level = 1
    if view in defn.weak_views:
        level = 0
    if visibility < 0.5:
        level -= 1
    return _CONF_ORDER[max(level, 0)]


def build_metrics(
    values: dict[str, float | None],
    stroke_type: str,
    family: str,
    view: str,
    visibility: dict[str, float],
    refs: ReferenceSet,
) -> list[Metric]:
    out: list[Metric] = []
    for mid, value in values.items():
        defn = METRICS[mid]
        entry, source = refs.lookup(stroke_type, family, mid)
        conf = _confidence(defn, view, visibility.get(mid, 1.0))
        rating, score, cue, reference = "info", None, None, None
        if value is not None and entry is not None:
            rating, score, direction = rate(value, entry["good"], entry["ok"])
            reference = Reference(good=tuple(entry["good"]), ok=tuple(entry["ok"]), source=source)
            if direction:
                cue = defn.cue_low if direction == "low" else defn.cue_high
                if cue is None:  # out of range on a side we don't coach
                    rating, score = "good", 100
        out.append(
            Metric(
                id=mid,
                label=defn.label,
                value=None if value is None else round(value, defn.decimals),
                unit=defn.unit,
                phase=defn.phase,
                rating=rating,
                score=score,
                confidence=conf,
                reference=reference,
                explanation=defn.explanation,
                cue=cue,
                joints=list(defn.joints),
            )
        )
    return out


def stroke_score(metrics: list[Metric]) -> int | None:
    num = den = 0.0
    for m in metrics:
        if m.score is None or m.confidence == "low":
            continue
        w = METRICS[m.id].weight * (0.6 if m.confidence == "medium" else 1.0)
        num += w * m.score
        den += w
    return int(round(num / den)) if den else None


def summarize(strokes: list[Stroke], max_priorities: int = 3) -> Summary:
    if not strokes:
        return Summary(
            overall_score=None,
            stroke_counts={},
            headline="No strokes detected.",
            priorities=[],
        )
    counts = Counter(s.type for s in strokes)
    per_family = Counter(s.family for s in strokes)
    # one priority per metric, even when it shows up in several stroke families
    groups: dict[str, list[tuple[Stroke, Metric]]] = defaultdict(list)
    for s in strokes:
        for m in s.metrics:
            if m.rating in ("needs_work", "fair") and m.confidence != "low" and m.cue:
                groups[m.id].append((s, m))

    ranked = []
    for mid, items in groups.items():
        deficit = float(np.mean([100 - (m.score or 0) for _, m in items]))
        eligible = sum(per_family[f] for f in {s.family for s, _ in items})
        share = len(items) / eligible
        ranked.append((METRICS[mid].weight * deficit * share**0.5, mid, items))
    ranked.sort(key=lambda r: r[0], reverse=True)

    priorities = []
    for _, mid, items in ranked[:max_priorities]:
        worst = min(items, key=lambda it: it[1].score or 0)
        priorities.append(
            Priority(
                metric_id=mid,
                title=METRICS[mid].label,
                cue=worst[1].cue or "",
                stroke_type=worst[0].type,
                stroke_indices=sorted(s.index for s, _ in items),
                severity="needs_work" if any(m.rating == "needs_work" for _, m in items) else "fair",
            )
        )

    scores = [s.score for s in strokes if s.score is not None]
    n = len(strokes)
    headline = f"{n} stroke{'s' if n != 1 else ''} analyzed."
    if priorities:
        headline += f" Biggest opportunity: {priorities[0].title.lower()}."
    else:
        headline += " Your technique looks solid on every checkpoint we measured."
    return Summary(
        overall_score=int(round(float(np.mean(scores)))) if scores else None,
        stroke_counts=dict(counts),
        headline=headline,
        priorities=priorities,
    )
