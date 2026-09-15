"""Synthetic swings: a stick figure whose upper body rotates and whose hitting
wrist sweeps an arc, so tests can check the pipeline without video or MediaPipe."""

from __future__ import annotations

import numpy as np

from tennis_ai.pipeline.skeleton import NUM_JOINTS, J, PoseSequence

BASE = {
    "nose": (0.0, 0.72, -0.06),
    "l_shoulder": (-0.18, 0.5, 0.0), "r_shoulder": (0.18, 0.5, 0.0),
    "l_elbow": (-0.22, 0.24, 0.0), "r_elbow": (0.22, 0.24, 0.0),
    "l_wrist": (-0.22, 0.0, 0.0), "r_wrist": (0.22, 0.0, 0.0),
    "l_hip": (-0.12, 0.0, 0.0), "r_hip": (0.12, 0.0, 0.0),
    "l_knee": (-0.13, -0.45, 0.02), "r_knee": (0.13, -0.45, 0.02),
    "l_ankle": (-0.2, -0.9, 0.0), "r_ankle": (0.2, -0.9, 0.0),
    "l_heel": (-0.2, -0.93, 0.05), "r_heel": (0.2, -0.93, 0.05),
    "l_foot": (-0.2, -0.95, -0.1), "r_foot": (0.2, -0.95, -0.1),
}
UPPER = ["nose", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist"]


def rot_y(p: np.ndarray, theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    out = p.copy()
    out[..., 0] = c * p[..., 0] + s * p[..., 2]
    out[..., 2] = -s * p[..., 0] + c * p[..., 2]
    return out


def swing_sequence(
    kind: str = "forehand",
    contacts_s: tuple[float, ...] = (1.5,),
    duration_s: float = 3.0,
    fps: float = 30.0,
    left_handed: bool = False,
    camera_yaw: float = 0.0,
    windup: bool = False,
) -> PoseSequence:
    n = int(duration_s * fps)
    t = np.arange(n) / fps
    base = np.array([BASE[j] for j in (list(BASE))], dtype=float)
    order = [J[j] for j in BASE]
    skel0 = np.zeros((NUM_JOINTS, 3))
    skel0[order] = base
    p3 = np.repeat(skel0[None], n, axis=0)

    # upper-body rotation: turned away before contact, rotating through it
    theta = np.zeros(n)
    arm_raise = np.zeros(n)
    for tc in contacts_s:
        s = 1 / (1 + np.exp(-(t - tc) / 0.08))                  # fast turn centred on contact
        window = np.exp(-((t - tc) / 0.9) ** 2)                 # only near this stroke
        theta += window * (np.radians(70) * (1 - s) + np.radians(-40) * s)
        arm_raise += window
    for j in UPPER:
        p3[:, J[j]] = rot_y(skel0[J[j]][None].repeat(n, 0), 0.0)
    hit = "r_wrist"
    shoulder = p3[:, J["r_shoulder"]]
    reach = np.array([0.55, -0.1, 0.0])
    if kind == "backhand":
        reach = np.array([-0.75, -0.1, 0.0])                    # racket taken back on the other side
    if kind == "serve":
        reach = np.array([0.1, 0.62, 0.0])
    arm = np.stack(
        [rot_y(reach * a, th) for a, th in zip(np.clip(arm_raise, 0.35, 1.0), theta, strict=True)]
    )
    if kind == "serve":
        # arm swings up in the vertical plane from the racket drop (wrist behind the
        # head, above the shoulder) to straight up at contact, then down
        s = 1 / (1 + np.exp(-(t - contacts_s[0]) / 0.07))
        phi_deg = 20 + 160 * s
        if windup:
            # arm hangs low, then snaps up into the racket drop 1.3 s before contact:
            # a second fast motion, with the wrist well below the head
            s0 = 1 / (1 + np.exp(-(t - (contacts_s[0] - 1.3)) / 0.07))
            phi_deg = phi_deg - 90 * (1 - s0)
        phi = np.radians(phi_deg)
        arm = 0.62 * np.stack([np.full(n, 0.1), np.sin(phi), -np.cos(phi)], -1)
    p3[:, J[hit]] = shoulder + arm
    p3[:, J["r_elbow"]] = shoulder + arm * 0.5
    for j in ["l_shoulder", "r_shoulder", "l_elbow", "nose", "l_wrist"]:
        p3[:, J[j]] = np.stack([rot_y(p3[i, J[j]], th * 0.9) for i, th in enumerate(theta)])
    if kind == "backhand":
        p3[:, J["l_wrist"]] = p3[:, J[hit]] + np.array([0.08, 0.0, 0.0])   # two hands together
    if kind == "serve":
        p3[:, J["l_wrist"]] = p3[:, J["l_shoulder"]] + np.array([0.0, 0.6, 0.0]) * (
            1 - np.clip((t[:, None] - contacts_s[0] + 0.2) * 3, 0, 1))
        knee_bend = 0.12 * np.exp(-((t - contacts_s[0] + 0.45) / 0.2) ** 2)
        for j in ("l_knee", "r_knee"):
            p3[:, J[j], 2] += knee_bend * 2.0

    p3 += np.random.default_rng(0).normal(0, 0.003, p3.shape)
    if camera_yaw:
        p3 = rot_y(p3, camera_yaw)
    if left_handed:
        from tennis_ai.pipeline.skeleton import MIRROR

        p3 = p3[:, MIRROR]
        p3[..., 0] *= -1

    width, height = 1280, 720
    kp2d = np.stack([0.5 + p3[..., 0] * 0.35, 0.55 - p3[..., 1] * 0.35 * width / height], -1)
    return PoseSequence(
        kp2d=kp2d.astype(np.float32),
        kp3d=p3.astype(np.float32),
        conf=np.full((n, NUM_JOINTS), 0.95, dtype=np.float32),
        valid=np.ones(n, dtype=bool),
        fps=fps,
        width=width,
        height=height,
        model="synthetic",
        bbox_height=np.full(n, 500.0, dtype=np.float32),
    )


def still_sequence(duration_s: float = 3.0, fps: float = 30.0) -> PoseSequence:
    seq = swing_sequence(contacts_s=(), duration_s=duration_s, fps=fps)
    return seq
