"""Optional Firebase ID-token verification."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Header

from ..config import Settings
from .errors import api_error

ANONYMOUS = "anonymous"


def make_auth_dependency(settings: Settings) -> Callable[..., str]:
    if not settings.auth_required:

        def no_auth() -> str:
            return ANONYMOUS

        return no_auth

    import firebase_admin
    from firebase_admin import auth

    if not firebase_admin._apps:
        options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None
        firebase_admin.initialize_app(options=options)

    def firebase_user(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise api_error(401, "unauthorized", "Sign in to analyze videos.")
        try:
            decoded = auth.verify_id_token(authorization.split(" ", 1)[1])
        except Exception as e:
            raise api_error(401, "unauthorized", "Your session expired. Sign in again.") from e
        return decoded["uid"]

    return firebase_user
