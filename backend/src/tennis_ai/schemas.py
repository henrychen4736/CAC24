"""API response models — the contract with the app (docs/ARCHITECTURE.md §6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Rating = Literal["good", "fair", "needs_work", "info"]
Confidence = Literal["high", "medium", "low"]
Bound = float | None


class QualityWarning(BaseModel):
    code: str
    message: str


class VideoMeta(BaseModel):
    duration_s: float
    fps: float
    width: int
    height: int
    frames_analyzed: int


class PlayerMeta(BaseModel):
    handedness: Literal["right", "left"]
    handedness_source: Literal["user", "detected", "default"]
    view: Literal["front", "back", "side", "oblique", "unknown"]
    view_confidence: float


class Quality(BaseModel):
    score: float
    warnings: list[QualityWarning] = []


class ModelsMeta(BaseModel):
    pose: str
    classifier: str
    reference: str


class Reference(BaseModel):
    good: tuple[Bound, Bound]
    ok: tuple[Bound, Bound]
    source: str


class Metric(BaseModel):
    id: str
    label: str
    value: float | None
    unit: str
    phase: str
    rating: Rating
    score: int | None
    confidence: Confidence
    reference: Reference | None
    explanation: str
    cue: str | None
    joints: list[str]


class Phase(BaseModel):
    name: str
    start_s: float
    end_s: float


class Stroke(BaseModel):
    index: int
    type: str
    family: Literal["forehand", "backhand", "overhead"]
    type_confidence: float
    type_source: Literal["heuristic", "model", "user"]
    start_s: float
    contact_s: float
    end_s: float
    key_frames: dict[str, float]
    phases: list[Phase]
    score: int | None
    skill_score: float | None
    metrics: list[Metric]


class Priority(BaseModel):
    metric_id: str
    title: str
    cue: str
    stroke_type: str
    stroke_indices: list[int]
    severity: Literal["needs_work", "fair"]


class Summary(BaseModel):
    overall_score: int | None
    stroke_counts: dict[str, int]
    headline: str
    priorities: list[Priority]


class PoseTrack(BaseModel):
    fps: float
    joints: list[str]
    edges: list[tuple[int, int]]
    frames: list[list[float] | None]


class AnalysisReport(BaseModel):
    version: str
    video: VideoMeta
    player: PlayerMeta
    quality: Quality
    models: ModelsMeta
    summary: Summary
    strokes: list[Stroke]
    pose_track: PoseTrack


JobStatus = Literal["queued", "processing", "done", "failed"]
JobStage = Literal["queued", "decoding", "pose", "analysis", "done"]


class JobError(BaseModel):
    code: str
    message: str


class Job(BaseModel):
    id: str
    status: JobStatus
    stage: JobStage
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    error: JobError | None = None
    result: AnalysisReport | None = None


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    pose_model: str
    classifier: str
    reference: str
    auth_required: bool
