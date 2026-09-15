"""Stroke type: learned ONNX model when available, heuristic otherwise."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import horizontal, joint, midpoint, unit
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
HINT_TO_FAMILY = {"forehand": "forehand", "backhand": "backhand", "serve": "overhead"}


@dataclass(frozen=True)
class TypeDecision:
    type: str
    family: str
    confidence: float
    source: str  # heuristic | model | user
    skill_score: float | None = None


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


@dataclass(frozen=True)
class HeuristicCues:
    wrist_above_head: float   # torso lengths, highest point just around contact
    toss_arm_up: float        # non-hitting wrist above head before contact, torso lengths
    racket_up_early: float    # hitting wrist vs shoulder just before contact, torso lengths
    side: float               # >0 hitting-hand side (forehand), <0 other side (backhand)
    hands_together: float     # mean wrist distance before contact, torso lengths


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

    # Which side the racket is on during the backswing. Near contact a backhand
    # crosses to the hitting side, so the cue must come from before that.
    back = sl(-0.8, -0.25)
    hip_c = midpoint(p, "l_hip", "r_hip")[back]
    wrist = joint(p, "r_wrist")[back] - hip_c
    hip_axis = unit(horizontal(joint(p, "r_hip")[back] - joint(p, "l_hip")[back]))
    sh_axis = unit(horizontal(joint(p, "r_shoulder")[back] - joint(p, "l_shoulder")[back]))
    side = _nan(np.median, (np.sum(wrist * hip_axis, -1) + np.sum(wrist * sh_axis, -1)) / 2) / t3

    grip = sl(-0.4, 0.05)
    together = _nan(
        np.mean, np.linalg.norm(joint(p, "l_wrist")[grip] - joint(p, "r_wrist")[grip], axis=-1)
    ) / t3
    return HeuristicCues(above, toss_up, early, side, together)


def _overhead_score(cues: HeuristicCues) -> float:
    """> 0 means overhead: high contact AND tossing arm went up AND racket was already high."""
    return min(
        np.nan_to_num(cues.wrist_above_head, nan=-1) - 0.1,
        np.nan_to_num(cues.toss_arm_up, nan=-1) - 0.15,
        np.nan_to_num(cues.racket_up_early, nan=-1) + 0.3,
    )


def is_overhead(cues: HeuristicCues) -> bool:
    return _overhead_score(cues) > 0


def fits_hint(cues: HeuristicCues, hint: str) -> bool:
    """Drop detections that can't be the stroke the user said they filmed.

    A serve contact is never well below the head; a groundstroke is never a
    clear overhead. This removes ball bounces and ready-position fidgets from
    serve videos without second-guessing plausible strokes.
    """
    family = HINT_TO_FAMILY.get(hint)
    if family == "overhead":
        return not (cues.wrist_above_head < -0.2)
    if family in ("forehand", "backhand"):
        return not (_overhead_score(cues) > 0.2)
    return True


def _default_type(family: str, cues: HeuristicCues) -> str:
    if family == "overhead":
        return "serve"
    if family == "backhand":
        return "backhand_2h" if cues.hands_together < 0.5 else "backhand_1h"
    return "forehand"


def heuristic_decision(prep: Prepared, w: StrokeWindow, hint: str = "auto") -> TypeDecision:
    cues = heuristic_cues(prep, w)
    overhead = _overhead_score(cues)
    if np.isnan([cues.wrist_above_head, cues.side]).any():
        family, conf = "forehand", 0.3
    elif overhead > 0:
        family, conf = "overhead", _sigmoid(overhead / 0.1)
    else:
        family = "forehand" if cues.side >= 0 else "backhand"
        conf = _sigmoid(abs(cues.side) / 0.1)
    hinted = HINT_TO_FAMILY.get(hint)
    if hinted and hinted != family:
        return TypeDecision(_default_type(hinted, cues), hinted, 1.0, "user")
    return TypeDecision(_default_type(family, cues), family, round(conf, 3), "heuristic")


class StrokeClassifier:
    """Wraps the ONNX multi-task model; falls back to the heuristic."""

    def __init__(self, session=None, meta: dict | None = None):
        self._session = session
        self._meta = meta or {}

    @property
    def name(self) -> str:
        if self._session is None:
            return "heuristic"
        return f"learned:{self._meta.get('model_version', 'v1')}"

    @classmethod
    def load(cls, onnx_path: Path) -> StrokeClassifier:
        meta_path = onnx_path.with_suffix(".json")
        if not onnx_path.exists() or not meta_path.exists():
            return cls()
        import onnxruntime as ort

        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        return cls(session, json.loads(meta_path.read_text()))

    def classify(self, prep: Prepared, w: StrokeWindow, hint: str = "auto") -> TypeDecision:
        heuristic = heuristic_decision(prep, w, hint)
        if self._session is None:
            return heuristic

        from ..ml.features import stroke_features

        x = stroke_features(prep, w.contact)
        mean = np.asarray(self._meta["feature_mean"], dtype=np.float32)
        std = np.asarray(self._meta["feature_std"], dtype=np.float32)
        x = ((x - mean) / std)[None].astype(np.float32)
        type_logits, skill_logit = self._session.run(None, {"x": x})
        classes: list[str] = self._meta["classes"]
        logits = type_logits[0].astype(np.float64)

        hinted = HINT_TO_FAMILY.get(hint)
        if hinted:
            mask = np.array([FAMILY_OF[k] == hinted for k in classes])
            logits = np.where(mask, logits, -np.inf)
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        k = int(np.argmax(probs))
        skill = _sigmoid(float(skill_logit.reshape(-1)[0]))
        return TypeDecision(
            type=classes[k],
            family=FAMILY_OF[classes[k]],
            confidence=round(float(probs[k]), 3),
            source="user" if hinted else "model",
            skill_score=round(skill, 3),
        )
