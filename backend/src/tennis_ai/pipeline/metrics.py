"""Biomechanical metrics per stroke family, and camera-view estimation.

All computations use the canonical right-handed skeleton produced by
``preprocess.prepare``. Rotations are *changes* in the direction of the
shoulder/hip line in the horizontal plane, so they don't depend on where the
camera stands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import (
    angle_from_vertical,
    finite,
    horizontal,
    joint,
    joint_angle,
    midpoint,
    unit,
    wrap_deg,
    yaw,
)
from .preprocess import Prepared
from .segment import swing_speed
from .skeleton import J


@dataclass(frozen=True)
class MetricDef:
    id: str
    label: str
    unit: str
    phase: str
    explanation: str
    cue_low: str | None
    cue_high: str | None
    joints: tuple[str, ...]
    key_frame: str
    weight: float = 1.0
    depth_sensitive: bool = False            # relies on MediaPipe's (noisier) depth estimate
    weak_views: frozenset[str] = field(default_factory=frozenset)  # unreliable from these views
    camera_sensitive: bool = False           # affected by a moving / panning camera
    ball_dependent: bool = False             # only meaningful when actually hitting a ball
    decimals: int = 1


_SH = ("l_shoulder", "r_shoulder")
_HIPS = ("l_hip", "r_hip")
_LEGS = ("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle")
_ARM = ("r_shoulder", "r_elbow", "r_wrist")
_TOSS = ("l_shoulder", "l_elbow", "l_wrist")

METRICS: dict[str, MetricDef] = {
    m.id: m
    for m in [
        MetricDef(
            "shoulder_rotation", "Shoulder rotation", "deg", "forward_swing",
            "How far your shoulders rotate from the end of the backswing to contact. "
            "Rotation, not the arm, is where racket speed comes from.",
            "Turn your shoulders fully in the backswing, then rotate them through so your "
            "chest faces the net at contact.",
            None, _SH, "contact", weight=1.2, depth_sensitive=True,
        ),
        MetricDef(
            "hip_shoulder_separation", "Hip–shoulder separation", "deg", "preparation",
            "Angle between your shoulder line and hip line at the end of the backswing: "
            "the 'coil' that stores energy.",
            "Coil your shoulders further than your hips in the backswing; that stretch is free power.",
            "Your upper body is twisting far past your hips; let the hips turn a little more "
            "with the shoulders.",
            _SH + _HIPS, "backswing_end", depth_sensitive=True,
        ),
        MetricDef(
            "knee_flexion", "Knee bend", "deg", "preparation",
            "Deepest knee bend while you load. Legs start the kinetic chain.",
            "Bend your knees more as you load, then push up from the ground into the ball.",
            "You're sitting very low; stay athletic but not squatted so you can move.",
            _LEGS, "load",
        ),
        MetricDef(
            "contact_in_front", "Contact point in front", "torso", "contact",
            "How far in front of your body you meet the ball, along the direction of the swing.",
            "Contact is late: meet the ball further in front of your front hip.",
            None, ("r_wrist",) + _HIPS, "contact", weight=1.5, depth_sensitive=True,
            weak_views=frozenset({"front", "back"}), decimals=2,
        ),
        MetricDef(
            "contact_elbow_angle", "Hitting-arm extension", "deg", "contact",
            "Elbow angle of your hitting arm at contact.",
            "Your arm is cramped at contact: give yourself more space from the ball.",
            None, _ARM, "contact",
        ),
        MetricDef(
            "finish_height", "Follow-through height", "torso", "follow_through",
            "Highest point of your hitting hand after contact, relative to your shoulders.",
            "Finish higher: let the racket follow through up and over your shoulder.",
            None, ("r_wrist",) + _SH, "finish", weight=0.8, decimals=2,
        ),
        MetricDef(
            "trunk_lean", "Balance at contact", "deg", "contact",
            "How far your upper body leans away from vertical at contact.",
            None,
            "You're leaning at contact: stay tall and balanced through the shot.",
            _SH + _HIPS, "contact", weight=0.8,
        ),
        MetricDef(
            "stance_width", "Stance width", "torso", "contact",
            "Distance between your feet at contact.",
            "Widen your base for balance and a stable platform to rotate on.",
            "Your stance is very wide, which can slow your recovery.",
            ("l_ankle", "r_ankle"), "contact", weight=0.6, weak_views=frozenset({"side"}),
            depth_sensitive=True, decimals=2,
        ),
        MetricDef(
            "head_stability", "Head stability", "torso", "contact",
            "How much your head moves through contact.",
            None,
            "Keep your head still through contact and watch the contact point.",
            ("nose",), "contact", weight=0.7, camera_sensitive=True, decimals=2,
        ),
        MetricDef(
            "swing_speed", "Swing speed", "torso/s", "forward_swing",
            "Peak speed of your hitting hand, in torso lengths per second.",
            "Accelerate more through contact: stay loose and let rotation whip the racket.",
            None, ("r_wrist",), "contact",
        ),
        MetricDef(
            "forward_swing_time", "Forward swing time", "s", "forward_swing",
            "Time from the end of your backswing to contact.",
            None, None, ("r_wrist",), "contact", decimals=2,
        ),
        MetricDef(
            "leg_drive", "Leg drive", "deg", "acceleration",
            "How much your knees extend from the deepest bend to contact.",
            "Drive up through the ball: extend your legs explosively into contact.",
            None, _LEGS, "contact", weight=1.2, ball_dependent=True,
        ),
        MetricDef(
            "trophy_elbow_height", "Hitting elbow at trophy", "torso", "preparation",
            "Height of your hitting elbow relative to your hitting shoulder in the trophy position.",
            "Lift your hitting elbow to about shoulder height in the trophy position.",
            "Your hitting elbow is very high at the trophy; keep it near shoulder level.",
            _ARM, "trophy", decimals=2,
        ),
        MetricDef(
            "toss_arm_extension", "Tossing-arm extension", "deg", "preparation",
            "Elbow angle of your tossing arm in the trophy position.",
            "Keep your tossing arm long and straight as you lift the ball.",
            None, _TOSS, "trophy",
        ),
        MetricDef(
            "shoulder_tilt", "Shoulder tilt at trophy", "deg", "preparation",
            "Angle of your shoulder line in the trophy position: tossing shoulder up, "
            "hitting shoulder down.",
            "Tilt your shoulders more in the trophy: tossing shoulder up, hitting shoulder down.",
            "Your shoulders are tilted a lot; that can pull the toss behind you.",
            _SH, "trophy",
        ),
        MetricDef(
            "contact_height", "Contact height", "torso", "contact",
            "How high above your head you make contact.",
            "Reach up and hit at full extension, well above your head.",
            None, ("r_wrist", "nose"), "contact", weight=1.2, decimals=2,
        ),
        MetricDef(
            "finish_across", "Follow-through across the body", "torso", "follow_through",
            "How far your hitting hand finishes across to the non-hitting side.",
            "Let the racket finish across your body on the non-hitting side.",
            None, ("r_wrist",) + _HIPS, "finish", weight=0.8, depth_sensitive=True,
            weak_views=frozenset({"side"}), decimals=2,
        ),
    ]
}

GROUNDSTROKE_METRICS = (
    "shoulder_rotation", "hip_shoulder_separation", "knee_flexion", "contact_in_front",
    "contact_elbow_angle", "finish_height", "trunk_lean", "stance_width", "head_stability",
    "swing_speed", "forward_swing_time",
)
OVERHEAD_METRICS = (
    "knee_flexion", "leg_drive", "trophy_elbow_height", "toss_arm_extension", "shoulder_tilt",
    "contact_height", "contact_elbow_angle", "finish_across", "swing_speed",
)


def _span(fps: float, n: int, center: int, a: float, b: float) -> slice:
    lo = max(0, center + int(round(a * fps)))
    hi = min(n, center + int(round(b * fps)) + 1)
    return slice(lo, max(hi, lo + 1))


def _knees(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return (
        joint_angle(p, "l_hip", "l_knee", "l_ankle"),
        joint_angle(p, "r_hip", "r_knee", "r_ankle"),
    )


def _nanmax(x) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.nanmax(x)) if np.isfinite(x).any() else float("nan")


def _nanmin(x) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.nanmin(x)) if np.isfinite(x).any() else float("nan")


def groundstroke_metrics(prep: Prepared, kf: dict[str, int]) -> dict[str, float | None]:
    p, fps, n, t3 = prep.p3, prep.fps, prep.num_frames, prep.torso3
    b, c, end = kf["backswing_end"], kf["contact"], kf["end"]
    sh = joint(p, "r_shoulder") - joint(p, "l_shoulder")
    hp = joint(p, "r_hip") - joint(p, "l_hip")
    hip_c = midpoint(p, "l_hip", "r_hip")
    sh_c = midpoint(p, "l_shoulder", "r_shoulder")
    wrist = joint(p, "r_wrist")
    speed = swing_speed(prep)

    kl, kr = _knees(p)
    load = _span(fps, n, c, (b - c) / fps - 0.3, 0.0)
    knee_flex = 180.0 - _nanmin(np.fmin(kl[load], kr[load]))

    lo, hi = max(c - 1, 0), min(c + 1, n - 1)
    fwd = unit(horizontal(wrist[hi] - wrist[lo]))
    in_front = float(np.dot(horizontal(wrist[c] - hip_c[c]), fwd)) / t3

    nose2 = prep.p2[:, J["nose"]]
    head = nose2[_span(fps, n, c, -0.1, 0.15)] - nose2[c]
    head_move = _nanmax(np.linalg.norm(head, axis=-1)) / prep.torso2

    return {
        "shoulder_rotation": abs(float(wrap_deg(yaw(sh[c]) - yaw(sh[b])))),
        "hip_shoulder_separation": abs(float(wrap_deg(yaw(sh[b]) - yaw(hp[b])))),
        "knee_flexion": knee_flex,
        "contact_in_front": in_front,
        "contact_elbow_angle": float(joint_angle(p, *_ARM)[c]),
        "finish_height": _nanmax(wrist[c : end + 1, 1] - sh_c[c : end + 1, 1]) / t3,
        "trunk_lean": float(angle_from_vertical(sh_c[c] - hip_c[c])),
        "stance_width": float(
            np.linalg.norm(horizontal(joint(p, "l_ankle")[c] - joint(p, "r_ankle")[c]))
        ) / t3,
        "head_stability": head_move,
        "swing_speed": _nanmax(speed[b : c + 3]),
        "forward_swing_time": (c - b) / fps,
    }


def overhead_metrics(prep: Prepared, kf: dict[str, int]) -> dict[str, float | None]:
    p, t3 = prep.p3, prep.torso3
    t, ld, c, f, end = kf["trophy"], kf["load"], kf["contact"], kf["finish"], kf["end"]
    kl, kr = _knees(p)
    leg = kl if np.nan_to_num(kl[ld], nan=180) <= np.nan_to_num(kr[ld], nan=180) else kr
    lsh, rsh = joint(p, "l_shoulder"), joint(p, "r_shoulder")
    hip_c = midpoint(p, "l_hip", "r_hip")
    hip_axis = unit(horizontal(joint(p, "r_hip") - joint(p, "l_hip")))
    lateral = np.sum((joint(p, "r_wrist") - hip_c) * hip_axis, axis=-1) / t3
    tilt = np.degrees(
        np.arctan2(lsh[t, 1] - rsh[t, 1], np.linalg.norm(horizontal(lsh[t] - rsh[t])))
    )
    return {
        "knee_flexion": 180.0 - float(leg[ld]),
        "leg_drive": _nanmax(leg[ld : c + 1]) - float(leg[ld]),
        "trophy_elbow_height": float(joint(p, "r_elbow")[t, 1] - rsh[t, 1]) / t3,
        "toss_arm_extension": float(joint_angle(p, *_TOSS)[t]),
        "shoulder_tilt": float(tilt),
        "contact_height": float(joint(p, "r_wrist")[c, 1] - joint(p, "nose")[c, 1]) / t3,
        "contact_elbow_angle": float(joint_angle(p, *_ARM)[c]),
        "finish_across": -_nanmin(lateral[c : max(f, end) + 1]),
        "swing_speed": _nanmax(swing_speed(prep)[t : c + 3]),
    }


def compute_metrics(prep: Prepared, kf: dict[str, int], family: str) -> dict[str, float | None]:
    raw = overhead_metrics(prep, kf) if family == "overhead" else groundstroke_metrics(prep, kf)
    return {k: finite(v) for k, v in raw.items()}


def metric_frame(defn: MetricDef, kf: dict[str, int]) -> int:
    if defn.key_frame in kf:
        return kf[defn.key_frame]
    if defn.key_frame == "load":
        return kf.get("backswing_end", kf["contact"])
    return kf["contact"]


# --------------------------------------------------------------------------- camera view


def estimate_view(prep: Prepared) -> tuple[str, float]:
    """Camera position relative to the player: front, back, side, or oblique.

    Shoulder width in the image (relative to torso length) separates frontal from
    side-on views; whether the nose is in front of the shoulders (toward the
    camera) separates front from back.
    """
    ok = prep.valid
    if ok.sum() < 3:
        return "unknown", 0.0
    p2, p3 = prep.p2[ok], prep.p3[ok]
    width = np.linalg.norm(p2[:, J["l_shoulder"]] - p2[:, J["r_shoulder"]], axis=-1) / prep.torso2
    ratio = float(np.nanmedian(width))
    shoulder_z = (p3[:, J["l_shoulder"], 2] + p3[:, J["r_shoulder"], 2]) / 2
    facing = float(np.nanmedian(p3[:, J["nose"], 2] - shoulder_z))  # > 0: nose toward camera
    if ratio >= 0.5:
        view = "front" if facing > 0 else "back"
        conf = min(1.0, (ratio - 0.5) / 0.2 + 0.5) * min(1.0, abs(facing) / 0.05 + 0.3)
    elif ratio <= 0.3:
        view, conf = "side", min(1.0, (0.3 - ratio) / 0.15 + 0.5)
    else:
        view, conf = "oblique", 0.6
    return view, round(float(np.clip(conf, 0.0, 1.0)), 2)
