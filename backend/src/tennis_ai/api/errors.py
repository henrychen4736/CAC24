"""HTTP errors in the contract's ``{"error": {"code", "message"}}`` shape."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail=message)
        self.code = code


def api_error(status: int, code: str, message: str) -> ApiError:
    return ApiError(status, code, message)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse({"error": {"code": exc.code, "message": exc.detail}}, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = f"{where}: {first.get('msg', 'invalid request')}" if where else "Invalid request."
        return JSONResponse({"error": {"code": "invalid_request", "message": msg}}, 422)

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse({"error": {"code": code, "message": str(exc.detail)}}, exc.status_code)
