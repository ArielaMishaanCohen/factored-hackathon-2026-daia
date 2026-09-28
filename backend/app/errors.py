"""Formato único de errores de la API (design.md 6.1)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

STATUS = {
    "UNAUTHENTICATED": 401,
    "SESSION_EXPIRED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "VALIDATION_ERROR": 422,
    "INTERNAL": 500,
}


class APIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def _body(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=STATUS[code], content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError):
        return _body(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _body("VALIDATION_ERROR", str(exc.errors()[:3]))

    @app.exception_handler(Exception)
    async def _internal(_: Request, exc: Exception):
        return _body("INTERNAL", "Error interno.")
