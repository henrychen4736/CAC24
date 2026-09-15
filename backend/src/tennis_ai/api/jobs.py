"""In-process job queue. Swap for Cloud Tasks / a real queue when scaling out."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..pipeline.errors import INTERNAL, AnalysisError
from ..schemas import AnalysisReport, Job, JobError

log = logging.getLogger(__name__)

_STAGE_WEIGHTS = {"queued": (0.0, 0.0), "decoding": (0.0, 0.02), "pose": (0.02, 0.9),
                  "analysis": (0.9, 0.99), "done": (1.0, 1.0)}


class AnalyzerLike(Protocol):
    def analyze(self, path: Path, stroke_hint: str, handedness: str, progress) -> AnalysisReport: ...


class _Record:
    def __init__(self, job: Job, owner: str, path: Path):
        self.job = job
        self.owner = owner
        self.path = path
        self.created = time.monotonic()


class JobManager:
    def __init__(self, analyzer: AnalyzerLike, workers: int = 1, ttl_seconds: int = 3600):
        self._analyzer = analyzer
        self._ttl = ttl_seconds
        self._jobs: dict[str, _Record] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="analysis")

    def submit(self, owner: str, path: Path, stroke_hint: str, handedness: str) -> Job:
        self._expire()
        job = Job(
            id=uuid.uuid4().hex,
            status="queued",
            stage="queued",
            progress=0.0,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._jobs[job.id] = _Record(job, owner, path)
        self._pool.submit(self._run, job.id, stroke_hint, handedness)
        return job.model_copy()

    def get(self, owner: str, job_id: str) -> Job | None:
        self._expire()
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None or rec.owner != owner:
                return None
            return rec.job.model_copy()

    def delete(self, owner: str, job_id: str) -> bool:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None or rec.owner != owner:
                return False
            del self._jobs[job_id]
        rec.path.unlink(missing_ok=True)
        return True

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ internals

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is not None:
                rec.job = rec.job.model_copy(update=fields)

    def _progress(self, job_id: str, stage: str, fraction: float) -> None:
        lo, hi = _STAGE_WEIGHTS.get(stage, (0.0, 1.0))
        self._update(job_id, status="processing", stage=stage,
                     progress=round(lo + (hi - lo) * max(0.0, min(fraction, 1.0)), 3))

    def _run(self, job_id: str, stroke_hint: str, handedness: str) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
        if rec is None:
            return
        try:
            self._progress(job_id, "decoding", 0.0)
            report = self._analyzer.analyze(
                rec.path, stroke_hint, handedness,
                lambda stage, frac: self._progress(job_id, stage, frac),
            )
            self._update(job_id, status="done", stage="done", progress=1.0, result=report)
        except AnalysisError as e:
            self._update(job_id, status="failed", error=JobError(code=e.code, message=e.message))
        except Exception:
            log.exception("analysis %s failed", job_id)
            self._update(job_id, status="failed", error=JobError(
                code=INTERNAL, message="Something went wrong while analyzing this video."))
        finally:
            rec.path.unlink(missing_ok=True)  # never keep user videos after processing

    def _expire(self) -> None:
        cutoff = time.monotonic() - self._ttl
        with self._lock:
            old = [k for k, r in self._jobs.items()
                   if r.created < cutoff and r.job.status in ("done", "failed")]
            for k in old:
                del self._jobs[k]
