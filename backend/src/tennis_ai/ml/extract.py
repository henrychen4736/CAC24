"""Run pose estimation over a dataset once and cache the results.

Pose estimation is the expensive step (seconds per clip). Everything after it
(features, metrics, training, calibration) reads the cache, so changing feature
or metric code never requires re-running pose.

Output: ``<out>/<clip-id>.npz`` per clip + ``<out>/index.csv`` with labels.
"""

from __future__ import annotations

import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..pipeline import video
from ..pipeline.pose import MediaPipePoseEstimator, ensure_pose_model
from ..pipeline.skeleton import PoseSequence

INDEX_FIELDS = ["file", "video", "stroke", "skill", "player", "handedness", "view"]


@dataclass(frozen=True)
class ClipSpec:
    video: Path
    stroke: str
    skill: str
    player: str
    handedness: str
    view: str = ""  # camera position if known (front/back/side); calibration trusts it over estimates

    @property
    def clip_id(self) -> str:
        return f"{self.video.parent.name}__{self.video.stem}"


def read_manifest(csv_path: Path) -> list[ClipSpec]:
    root = csv_path.parent
    with csv_path.open(newline="") as f:
        return [
            ClipSpec(
                video=(root / row["video"]).resolve(),
                stroke=row.get("stroke", "").strip(),
                skill=row.get("skill", "").strip(),
                player=row.get("player", "").strip(),
                handedness=(row.get("handedness") or "").strip() or "auto",
                view=(row.get("view") or "").strip(),
            )
            for row in csv.DictReader(f)
        ]


def save_sequence(seq: PoseSequence, dest: Path) -> None:
    np.savez_compressed(
        dest, kp2d=seq.kp2d, kp3d=seq.kp3d, conf=seq.conf, valid=seq.valid,
        bbox_height=seq.bbox_height, fps=seq.fps, width=seq.width, height=seq.height,
        model=seq.model,
    )


def load_sequence(path: Path) -> PoseSequence:
    d = np.load(path)
    return PoseSequence(
        kp2d=d["kp2d"], kp3d=d["kp3d"], conf=d["conf"], valid=d["valid"],
        fps=float(d["fps"]), width=int(d["width"]), height=int(d["height"]),
        model=str(d["model"]), bbox_height=d["bbox_height"],
    )


_estimator: MediaPipePoseEstimator | None = None


def _init_worker(model_path: str, variant: str) -> None:
    global _estimator
    os.environ.setdefault("GLOG_minloglevel", "2")
    _estimator = MediaPipePoseEstimator(Path(model_path), variant, num_poses=2)


def _extract(spec: ClipSpec, dest: Path, max_seconds: float) -> tuple[str, str]:
    try:
        info = video.probe(spec.video)
        assert _estimator is not None
        seq = _estimator.estimate(
            video.iter_frames(spec.video, info, max_seconds), info.fps, info.width, info.height
        )
        save_sequence(seq, dest)
        return spec.clip_id, f"ok ({seq.valid.mean():.0%} frames with a player)"
    except Exception as e:  # keep going; one broken clip shouldn't stop a dataset run
        return spec.clip_id, f"error: {e}"


def extract(
    specs: list[ClipSpec],
    out: Path,
    models_dir: Path,
    variant: str = "heavy",
    workers: int | None = None,
    max_seconds: float = 30.0,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    model_path = ensure_pose_model(models_dir / f"pose_landmarker_{variant}.task", variant)
    todo = [s for s in specs if not (out / f"{s.clip_id}.npz").exists()]
    workers = workers or max(1, (os.cpu_count() or 2) // 2)
    print(f"{len(specs)} clips, {len(specs) - len(todo)} cached, extracting {len(todo)} "
          f"with {workers} workers ({variant} model)", flush=True)
    t0 = time.time()
    if todo:
        with ProcessPoolExecutor(workers, initializer=_init_worker,
                                 initargs=(str(model_path), variant)) as pool:
            futs = [pool.submit(_extract, s, out / f"{s.clip_id}.npz", max_seconds) for s in todo]
            for i, fut in enumerate(as_completed(futs), 1):
                clip_id, status = fut.result()
                if status.startswith("error") or i % 25 == 0 or i == len(todo):
                    rate = i / (time.time() - t0)
                    eta = (len(todo) - i) / rate / 60
                    print(f"  [{i}/{len(todo)}] {clip_id}: {status}  ({eta:.0f} min left)", flush=True)

    with (out / "index.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(INDEX_FIELDS)
        for s in specs:
            if (out / f"{s.clip_id}.npz").exists():
                w.writerow([f"{s.clip_id}.npz", s.video.as_posix(), s.stroke, s.skill, s.player,
                            s.handedness, s.view])
    print(f"Wrote {out / 'index.csv'}", flush=True)


def read_index(pose_dir: Path) -> list[dict]:
    with (pose_dir / "index.csv").open(newline="") as f:
        return list(csv.DictReader(f))
