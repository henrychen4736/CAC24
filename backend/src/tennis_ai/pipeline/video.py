"""Video decoding with frame-rate capping and resizing."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .errors import VIDEO_TOO_LONG, VIDEO_UNREADABLE, AnalysisError


@dataclass(frozen=True)
class VideoInfo:
    fps: float          # effective fps after frame skipping
    source_fps: float
    step: int           # keep every `step`-th source frame
    width: int          # size after resizing (and rotation, which OpenCV applies)
    height: int
    frame_count: int    # estimated number of frames we will yield (0 if unknown)
    duration_s: float


def _open(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise AnalysisError(VIDEO_UNREADABLE, "The video could not be opened.")
    return cap


def probe(path: Path, max_side: int = 960, max_fps: float = 60.0) -> VideoInfo:
    cap = _open(path)
    try:
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        raise AnalysisError(VIDEO_UNREADABLE, "The video contains no readable frames.")
    if not source_fps or source_fps <= 1 or source_fps > 1000:
        source_fps = 30.0  # some containers don't report fps; assume the common default
    step = max(1, round(source_fps / max_fps))
    h, w = frame.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    count = max(count, 0)
    return VideoInfo(
        fps=source_fps / step,
        source_fps=source_fps,
        step=step,
        width=int(round(w * scale)),
        height=int(round(h * scale)),
        frame_count=count // step if count else 0,
        duration_s=count / source_fps if count else 0.0,
    )


def iter_frames(path: Path, info: VideoInfo, max_seconds: float) -> Iterator[np.ndarray]:
    """Yield RGB frames at ``info.fps``, resized to ``info.width`` x ``info.height``."""
    if info.duration_s > max_seconds + 0.5:
        raise AnalysisError(
            VIDEO_TOO_LONG,
            f"The video is {info.duration_s:.0f}s long; the limit is {max_seconds:.0f}s. "
            "Trim it to the strokes you want analyzed.",
        )
    max_frames = int(max_seconds * info.fps) + 1
    cap = _open(path)
    try:
        src_index = 0
        yielded = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if src_index % info.step == 0:
                if yielded >= max_frames:
                    raise AnalysisError(
                        VIDEO_TOO_LONG, f"The video is longer than {max_seconds:.0f}s."
                    )
                if frame.shape[1] != info.width or frame.shape[0] != info.height:
                    frame = cv2.resize(frame, (info.width, info.height), interpolation=cv2.INTER_AREA)
                yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                yielded += 1
            src_index += 1
    finally:
        cap.release()
