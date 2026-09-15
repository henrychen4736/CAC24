"""End-to-end analysis: video file → AnalysisReport."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from .. import REPORT_VERSION
from ..config import Settings
from ..schemas import (
    AnalysisReport,
    ModelsMeta,
    Phase,
    PlayerMeta,
    PoseTrack,
    Quality,
    QualityWarning,
    Stroke,
    VideoMeta,
)
from . import video
from .classify import StrokeClassifier, fits_hint, heuristic_cues, is_overhead
from .errors import NO_PLAYER_DETECTED, AnalysisError
from .feedback import ReferenceSet, build_metrics, load_references, stroke_score, summarize
from .metrics import METRICS, compute_metrics, estimate_view, metric_frame
from .phases import key_frames, phases
from .pose import MediaPipePoseEstimator
from .preprocess import Prepared, prepare
from .segment import detect_strokes
from .skeleton import EDGES, JOINTS, J, PoseSequence

ProgressFn = Callable[[str, float], None]


class Analyzer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pose = MediaPipePoseEstimator(
            settings.pose_model_path, settings.pose_model, settings.pose_num_candidates
        )
        self.classifier = StrokeClassifier.load(settings.stroke_model_path)
        self.references = load_references(settings.calibrated_reference_path)

    def analyze(
        self,
        path: Path,
        stroke_hint: str = "auto",
        handedness: str = "auto",
        progress: ProgressFn | None = None,
    ) -> AnalysisReport:
        report = progress or (lambda stage, frac: None)
        s = self.settings
        report("decoding", 0.0)
        info = video.probe(path, s.max_side_px, s.max_fps)
        expected = info.frame_count or int(s.max_video_seconds * info.fps)
        report("pose", 0.0)
        seq = self.pose.estimate(
            video.iter_frames(path, info, s.max_video_seconds),
            info.fps,
            info.width,
            info.height,
            on_progress=lambda i: report("pose", min(i / max(expected, 1), 0.99)),
        )
        report("analysis", 0.0)
        return build_report(
            seq, stroke_hint, handedness, self.classifier, self.references,
            expose_skill=s.expose_skill_score,
        )


def _visibility(prep: Prepared, kf: dict[str, int]) -> dict[str, float]:
    out = {}
    for mid, defn in METRICS.items():
        f = metric_frame(defn, kf)
        idx = [J[j] for j in defn.joints]
        out[mid] = float(prep.conf[f, idx].mean())
    return out


def _quality(seq: PoseSequence, prep: Prepared, n_strokes: int) -> Quality:
    warnings: list[QualityWarning] = []
    score = 1.0
    if seq.fps < 24:
        warnings.append(QualityWarning(
            code="low_fps",
            message="Low frame rate. Record at 30 fps or higher; 60 fps is best for fast swings.",
        ))
        score -= 0.25
    detected = seq.valid.mean() if seq.num_frames else 0.0
    if detected < 0.7:
        warnings.append(QualityWarning(
            code="partial_detection",
            message="You weren't visible for part of the video. Keep your whole body in frame.",
        ))
        score -= 0.2
    heights = seq.bbox_height[seq.valid]
    if heights.size and np.median(heights) / seq.height < 0.25:
        warnings.append(QualityWarning(
            code="player_small",
            message="You're small in the frame. Move the camera closer so your body fills about "
            "half the frame height.",
        ))
        score -= 0.2
    if n_strokes and prep.handedness_source == "default":
        warnings.append(QualityWarning(
            code="handedness_uncertain",
            message="We couldn't tell which hand you hit with, so we assumed right-handed. "
            "Set your handedness in your profile.",
        ))
        score -= 0.1
    if n_strokes == 0:
        warnings.append(QualityWarning(
            code="no_strokes",
            message="No swings detected. Make sure the whole swing is in frame and film from "
            "the side or behind.",
        ))
    return Quality(score=round(max(score, 0.0), 2), warnings=warnings)


def pose_track(seq: PoseSequence) -> PoseTrack:
    frames: list[list[float] | None] = []
    for f in range(seq.num_frames):
        if not seq.valid[f]:
            frames.append(None)
            continue
        frames.append([round(float(v), 3) for v in seq.kp2d[f].reshape(-1)])
    return PoseTrack(fps=round(seq.fps, 3), joints=list(JOINTS), edges=list(EDGES), frames=frames)


def build_report(
    seq: PoseSequence,
    stroke_hint: str,
    handedness: str,
    classifier: StrokeClassifier,
    references: ReferenceSet,
    expose_skill: bool = False,
) -> AnalysisReport:
    """``expose_skill``: include the model's expert-likeness score (see Settings)."""
    if seq.valid.sum() < max(5, int(0.1 * seq.num_frames)):
        raise AnalysisError(
            NO_PLAYER_DETECTED,
            "We couldn't find a player in this video. Make sure your whole body is visible.",
        )
    prep = prepare(seq, handedness)
    view, view_conf = estimate_view(prep)
    fps = seq.fps
    t = lambda i: round(i / fps, 3)  # noqa: E731

    def plausible(w) -> bool:
        return fits_hint(heuristic_cues(prep, w), stroke_hint)

    def overhead(w) -> bool:
        return is_overhead(heuristic_cues(prep, w))

    strokes: list[Stroke] = []
    for w in detect_strokes(prep, accept=plausible, overhead=overhead):
        decision = classifier.classify(prep, w, stroke_hint)
        kf = key_frames(prep, w, decision.family)
        values = compute_metrics(prep, kf, decision.family)
        metrics = build_metrics(
            values, decision.type, decision.family, view, _visibility(prep, kf), references
        )
        strokes.append(
            Stroke(
                index=len(strokes),
                type=decision.type,
                family=decision.family,
                type_confidence=decision.confidence,
                type_source=decision.source,
                start_s=t(kf["start"]),
                contact_s=t(kf["contact"]),
                end_s=t(kf["end"]),
                key_frames={k: t(v) for k, v in kf.items() if k not in ("start", "end")},
                phases=[Phase(**p) for p in phases(kf, decision.family, fps)],
                score=stroke_score(metrics),
                skill_score=decision.skill_score if expose_skill else None,
                metrics=metrics,
            )
        )

    return AnalysisReport(
        version=REPORT_VERSION,
        video=VideoMeta(
            duration_s=round(seq.duration_s, 3),
            fps=round(fps, 3),
            width=seq.width,
            height=seq.height,
            frames_analyzed=seq.num_frames,
        ),
        player=PlayerMeta(
            handedness=prep.handedness,
            handedness_source=prep.handedness_source,
            view=view,
            view_confidence=view_conf,
        ),
        quality=_quality(seq, prep, len(strokes)),
        models=ModelsMeta(pose=seq.model, classifier=classifier.name, reference=references.source),
        summary=summarize(strokes),
        strokes=strokes,
        pose_track=pose_track(seq),
    )
