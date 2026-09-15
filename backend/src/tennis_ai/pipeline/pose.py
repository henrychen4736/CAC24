"""Pose estimation with MediaPipe Pose Landmarker and main-player tracking.

MediaPipe can return several people per frame (a coach, an opponent, someone
walking past). We keep every candidate, link candidates into tracks by
bounding-box continuity, and return the track of the main player: the one with
the largest (size x visibility x duration) score, extended by any fragments that
continue it after a detection gap.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .skeleton import MEDIAPIPE_INDEX, PoseSequence

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task"
)

ProgressFn = Callable[[int], None]


def ensure_pose_model(path: Path, variant: str) -> Path:
    """Download the MediaPipe model file on first use."""
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL.format(v=variant), tmp)
    tmp.replace(path)
    return path


@dataclass
class _Candidate:
    kp2d: np.ndarray   # (17, 2) normalized
    kp3d: np.ndarray   # (17, 3) canonical world coords
    conf: np.ndarray   # (17,)
    center: np.ndarray  # (2,) px
    height: float       # bbox height px
    score: float        # height x mean visibility


@dataclass
class _Track:
    members: dict[int, _Candidate] = field(default_factory=dict)

    @property
    def first(self) -> int:
        return min(self.members)

    @property
    def last(self) -> int:
        return max(self.members)

    @property
    def score(self) -> float:
        return sum(c.score for c in self.members.values())


def _candidate(landmarks, world, width: int, height: int) -> _Candidate:
    all2d = np.array([(p.x, p.y) for p in landmarks], dtype=np.float32)
    vis = np.array([p.visibility or 0.0 for p in landmarks], dtype=np.float32)
    kp2d = all2d[list(MEDIAPIPE_INDEX)]
    conf = vis[list(MEDIAPIPE_INDEX)]
    w3 = np.array([(p.x, p.y, p.z) for p in world], dtype=np.float32)[list(MEDIAPIPE_INDEX)]
    # MediaPipe world: x right, y down, z away from camera -> ours: x right, y up, z toward camera
    kp3d = w3 * np.array([1.0, -1.0, -1.0], dtype=np.float32)

    px = all2d * np.array([width, height], dtype=np.float32)
    seen = px[vis > 0.3] if (vis > 0.3).sum() >= 4 else px
    lo, hi = seen.min(axis=0), seen.max(axis=0)
    h = float(max(hi[1] - lo[1], 1.0))
    return _Candidate(kp2d, kp3d, conf, (lo + hi) / 2, h, h * float(conf.mean()))


def link_tracks(frames: list[list[_Candidate]], fps: float) -> list[_Track]:
    """Greedy frame-to-frame association by centre distance relative to body height."""
    max_gap = max(1, int(0.5 * fps))
    tracks: list[_Track] = []
    for f, cands in enumerate(frames):
        active = [t for t in tracks if f - t.last <= max_gap]
        pairs = []
        for ci, c in enumerate(cands):
            for ti, t in enumerate(active):
                prev = t.members[t.last]
                d = np.linalg.norm(c.center - prev.center) / max(prev.height, 1.0)
                size_ratio = c.height / max(prev.height, 1.0)
                if d < 0.6 and 0.5 < size_ratio < 2.0:
                    pairs.append((d, ci, ti))
        used_c, used_t = set(), set()
        for _, ci, ti in sorted(pairs):
            if ci in used_c or ti in used_t:
                continue
            active[ti].members[f] = cands[ci]
            used_c.add(ci)
            used_t.add(ti)
        for ci, c in enumerate(cands):
            if ci not in used_c:
                tracks.append(_Track({f: c}))
    return tracks


def select_player(tracks: list[_Track]) -> _Track | None:
    """Best-scoring track, extended with non-overlapping fragments that continue it."""
    if not tracks:
        return None
    tracks = sorted(tracks, key=lambda t: t.score, reverse=True)
    main = _Track(dict(tracks[0].members))
    for t in tracks[1:]:
        if t.score < 0.05 * main.score:
            continue
        if any(f in main.members for f in t.members):
            continue
        # fragment must be spatially continuous with the main track at its nearest boundary
        if t.first > main.last:
            a, b = main.members[main.last], t.members[t.first]
        elif t.last < main.first:
            a, b = main.members[main.first], t.members[t.last]
        else:
            # fills a gap inside the main track: compare with the frame just before it
            before = max(f for f in main.members if f < t.first)
            a, b = main.members[before], t.members[t.first]
        if np.linalg.norm(a.center - b.center) / max(a.height, 1.0) < 1.0:
            main.members.update(t.members)
    return main


class MediaPipePoseEstimator:
    def __init__(self, model_path: Path, variant: str = "heavy", num_poses: int = 2):
        self.model_path = model_path
        self.variant = variant
        self.num_poses = num_poses
        self.name = f"mediapipe-pose-landmarker-{variant}"

    def estimate(
        self,
        frames: Iterable[np.ndarray],
        fps: float,
        width: int,
        height: int,
        on_progress: ProgressFn | None = None,
    ) -> PoseSequence:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        ensure_pose_model(self.model_path, self.variant)
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=self.num_poses,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        per_frame: list[list[_Candidate]] = []
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            for i, rgb in enumerate(frames):
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
                result = landmarker.detect_for_video(image, int(round(i * 1000.0 / fps)))
                per_frame.append(
                    [
                        _candidate(lm, wl, width, height)
                        for lm, wl in zip(
                            result.pose_landmarks, result.pose_world_landmarks, strict=False
                        )
                    ]
                )
                if on_progress and i % 10 == 0:
                    on_progress(i)
        return build_sequence(per_frame, fps, width, height, self.name)


def build_sequence(
    per_frame: list[list[_Candidate]], fps: float, width: int, height: int, model: str
) -> PoseSequence:
    seq = PoseSequence.empty(len(per_frame), fps, width, height, model)
    player = select_player(link_tracks(per_frame, fps))
    if player is None:
        return seq
    for f, c in player.members.items():
        seq.kp2d[f] = c.kp2d
        seq.kp3d[f] = c.kp3d
        seq.conf[f] = c.conf
        seq.valid[f] = True
        seq.bbox_height[f] = c.height
    return seq
