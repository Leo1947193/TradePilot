from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.api import AnalyzeRequest, AnalysisResponse, ErrorDetail, ErrorObject, ErrorResponse


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorObject(
            code=code,
            message=message,
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", exclude_none=True),
    )


def _field_from_location(location: tuple[Any, ...]) -> str:
    parts = [str(part) for part in location if part != "body"]
    return ".".join(parts) if parts else "body"


def _invalid_request_message(details: list[ErrorDetail]) -> str:
    if len(details) == 1 and details[0].reason == "missing":
        return f"{details[0].field} is required"
    if any(detail.reason == "invalid_json" for detail in details):
        return "request body is not valid JSON"
    return "request contains invalid fields"


def _validation_details(exc: RequestValidationError) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []

    for error in exc.errors():
        reason = error["type"]
        if reason == "json_invalid":
            reason = "invalid_json"

        details.append(
            ErrorDetail(
                field=_field_from_location(error["loc"]),
                reason=reason,
            )
        )

    return details


app = FastAPI(
    title="TradePilot API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request
    details = _validation_details(exc)
    return _build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_request",
        message=_invalid_request_message(details),
        details=details,
    )


@app.post(
    "/api/v1/analyses",
    response_model=AnalysisResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def create_analysis(_: AnalyzeRequest) -> JSONResponse:
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="analysis pipeline is not implemented",
    )
