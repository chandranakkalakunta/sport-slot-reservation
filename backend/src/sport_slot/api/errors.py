import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sport_slot.api import error_codes
from sport_slot.middleware.request_id import get_request_id


class ApiError(Exception):
    """Domain error carrying a registry code (ADR-0006)."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _envelope(code: str, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "request_id": get_request_id(),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_envelope(error_codes.VALIDATION_FAILED, "Request validation failed"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code = error_codes.HTTP_ERROR_CODES.get(exc.status_code, error_codes.INTERNAL_ERROR)
        return JSONResponse(status_code=exc.status_code, content=_envelope(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_envelope(error_codes.INTERNAL_ERROR, "Internal server error"),
        )
