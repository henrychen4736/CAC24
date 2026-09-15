"""Canonical 17-joint skeleton and the pose sequence container.

3D convention (after conversion from MediaPipe world landmarks):
    metres, origin at the hip centre, x = image right, y = up, z = toward the camera.
The horizontal plane is x–z; rotations about the vertical axis are measured there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

JOINTS: tuple[str, ...] = (
    "nose",
    "l_shoulder", "r_shoulder",
    "l_elbow", "r_elbow",
    "l_wrist", "r_wrist",
    "l_hip", "r_hip",
    "l_knee", "r_knee",
    "l_ankle", "r_ankle",
    "l_heel", "r_heel",
    "l_foot", "r_foot",
)
J: dict[str, int] = {name: i for i, name in enumerate(JOINTS)}
NUM_JOINTS = len(JOINTS)

# Index of each canonical joint in MediaPipe's 33-landmark pose model.
MEDIAPIPE_INDEX: tuple[int, ...] = (0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32)

EDGES: tuple[tuple[int, int], ...] = (
    (J["l_shoulder"], J["r_shoulder"]),
    (J["l_shoulder"], J["l_elbow"]), (J["l_elbow"], J["l_wrist"]),
    (J["r_shoulder"], J["r_elbow"]), (J["r_elbow"], J["r_wrist"]),
    (J["l_shoulder"], J["l_hip"]), (J["r_shoulder"], J["r_hip"]),
    (J["l_hip"], J["r_hip"]),
    (J["l_hip"], J["l_knee"]), (J["l_knee"], J["l_ankle"]),
    (J["r_hip"], J["r_knee"]), (J["r_knee"], J["r_ankle"]),
    (J["l_ankle"], J["l_heel"]), (J["l_heel"], J["l_foot"]), (J["l_ankle"], J["l_foot"]),
    (J["r_ankle"], J["r_heel"]), (J["r_heel"], J["r_foot"]), (J["r_ankle"], J["r_foot"]),
)


def _mirror_permutation() -> np.ndarray:
    perm = []
    for name in JOINTS:
        if name.startswith("l_"):
            perm.append(J["r_" + name[2:]])
        elif name.startswith("r_"):
            perm.append(J["l_" + name[2:]])
        else:
            perm.append(J[name])
    return np.array(perm)


MIRROR = _mirror_permutation()


@dataclass
class PoseSequence:
    """Per-frame keypoints of the tracked player.

    kp2d:  (T, J, 2) image coordinates normalized to [0, 1] (x right, y down)
    kp3d:  (T, J, 3) world coordinates in metres (see module docstring)
    conf:  (T, J)    landmark visibility in [0, 1]
    valid: (T,)      the player was detected in this frame
    """

    kp2d: np.ndarray
    kp3d: np.ndarray
    conf: np.ndarray
    valid: np.ndarray
    fps: float
    width: int
    height: int
    model: str = "unknown"
    bbox_height: np.ndarray = field(default_factory=lambda: np.zeros(0))  # (T,) px, 0 if missing

    @property
    def num_frames(self) -> int:
        return int(self.valid.shape[0])

    @property
    def duration_s(self) -> float:
        return self.num_frames / self.fps if self.fps else 0.0

    @classmethod
    def empty(cls, num_frames: int, fps: float, width: int, height: int, model: str = "unknown"):
        return cls(
            kp2d=np.full((num_frames, NUM_JOINTS, 2), np.nan, dtype=np.float32),
            kp3d=np.full((num_frames, NUM_JOINTS, 3), np.nan, dtype=np.float32),
            conf=np.zeros((num_frames, NUM_JOINTS), dtype=np.float32),
            valid=np.zeros(num_frames, dtype=bool),
            fps=fps,
            width=width,
            height=height,
            model=model,
            bbox_height=np.zeros(num_frames, dtype=np.float32),
        )
