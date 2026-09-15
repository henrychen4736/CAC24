"""FastAPI application: upload → job → poll."""

# No `from __future__ import annotations` here: FastAPI resolves the endpoint
# annotations at definition time, and `User` is a closure-local alias.
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..config import Settings, get_settings
from ..pipeline.errors import UNSUPPORTED_FORMAT, VIDEO_TOO_LARGE
from ..schemas import Health, Job
from .auth import make_auth_dependency
from .errors import api_error, install_error_handlers
from .jobs import JobManager

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv", ".ogv", ".3gp"}
CHUNK = 1 << 20


def create_app(settings: Settings | None = None, analyzer=None) -> FastAPI:
    settings = settings or get_settings()
    state: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal analyzer
        if analyzer is None:
            from ..pipeline.analyzer import Analyzer

            analyzer = Analyzer(settings)
        state["analyzer"] = analyzer
        state["jobs"] = JobManager(analyzer, settings.workers, settings.job_ttl_seconds)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        yield
        state["jobs"].shutdown()

    app = FastAPI(
        title="Henry Tennis Analysis API",
        version=__version__,
        lifespan=lifespan,
        description="Upload a tennis video, poll the job, get technique feedback.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    current_user = make_auth_dependency(settings)

    @app.get("/v1/health", response_model=Health)
    def health() -> Health:
        a = state["analyzer"]
        return Health(
            status="ok",
            version=__version__,
            pose_model=a.pose.name,
            classifier=a.classifier.name,
            reference=a.references.source,
            auth_required=settings.auth_required,
        )

    User = Annotated[str, Depends(current_user)]

    @app.post("/v1/analyses", response_model=Job, status_code=202)
    async def create_analysis(
        file: Annotated[UploadFile, File()],
        user: User,
        stroke_hint: Annotated[Literal["auto", "forehand", "backhand", "serve"], Form()] = "auto",
        handedness: Annotated[Literal["auto", "right", "left"], Form()] = "auto",
    ) -> Job:
        suffix = Path(file.filename or "").suffix.lower()
        is_video = (file.content_type or "").startswith("video/")
        if suffix not in VIDEO_EXTENSIONS and not is_video:
            raise api_error(415, UNSUPPORTED_FORMAT, "Upload a video file (MP4, MOV, WebM, AVI…).")

        limit = settings.max_upload_mb * CHUNK
        size = 0
        with tempfile.NamedTemporaryFile(
            dir=settings.upload_dir, suffix=suffix or ".mp4", delete=False
        ) as tmp:
            path = Path(tmp.name)
            try:
                while chunk := await file.read(CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise api_error(
                            413, VIDEO_TOO_LARGE,
                            f"Videos must be under {settings.max_upload_mb} MB.",
                        )
                    tmp.write(chunk)
            except BaseException:
                tmp.close()
                path.unlink(missing_ok=True)
                raise
        return state["jobs"].submit(user, path, stroke_hint, handedness)

    @app.get("/v1/analyses/{job_id}", response_model=Job)
    def get_analysis(job_id: str, user: User) -> Job:
        job = state["jobs"].get(user, job_id)
        if job is None:
            raise api_error(404, "not_found", "That analysis doesn't exist or has expired.")
        return job

    @app.delete("/v1/analyses/{job_id}", status_code=204)
    def delete_analysis(job_id: str, user: User) -> Response:
        if not state["jobs"].delete(user, job_id):
            raise api_error(404, "not_found", "That analysis doesn't exist or has expired.")
        return Response(status_code=204)

    return app
