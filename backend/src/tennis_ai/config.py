"""Service configuration (environment variables prefixed ``TENNIS_``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENNIS_", env_file=".env", extra="ignore")

    # Models
    models_dir: Path = BACKEND_ROOT / "models"
    pose_model: Literal["lite", "full", "heavy"] = "heavy"
    pose_num_candidates: int = 2  # people detected per frame; we then track the main player
    # The model's expert-vs-beginner head is trained on THETIS shadow swings and
    # rates real on-court strokes, even a coach's, as beginner-like. Keep it out
    # of reports until it has been validated on real footage.
    expose_skill_score: bool = False

    # Video limits
    max_video_seconds: float = 60.0
    max_upload_mb: int = 300
    max_side_px: int = 960
    max_fps: float = 60.0

    # Service
    workers: int = 1
    job_ttl_seconds: int = 3600
    upload_dir: Path = BACKEND_ROOT / "uploads"
    auth_required: bool = False
    firebase_project_id: str | None = None
    cors_origins: list[str] = ["*"]

    @property
    def pose_model_path(self) -> Path:
        return self.models_dir / f"pose_landmarker_{self.pose_model}.task"

    @property
    def stroke_model_path(self) -> Path:
        return self.models_dir / "stroke_model.onnx"

    @property
    def calibrated_reference_path(self) -> Path:
        return self.models_dir / "reference_calibrated.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
