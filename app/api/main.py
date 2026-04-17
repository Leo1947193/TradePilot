from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.db.pool import close_connection_pool, create_connection_pool, open_connection_pool
from app.graph.builder import build_analysis_graph
from app.repositories.analysis_reports import AnalysisReportRepository
from app.repositories.postgresql_analysis_reports import PostgreSQLAnalysisReportRepository
from app.schemas.api import AnalyzeRequest, AnalysisResponse, ErrorDetail, ErrorObject, ErrorResponse
from app.schemas.graph_state import TradePilotState


@dataclass
class RepositoryUnavailableError(RuntimeError):
    message: str = "analysis report repository is unavailable"


class UnavailableAnalysisReportRepository:
    def __init__(self, message: str = "analysis report repository is unavailable") -> None:
        self._message = message

    def save_analysis_report(self, payload: Any) -> Any:
        del payload
        raise RepositoryUnavailableError(self._message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.postgres_pool = None
    app.state.analysis_report_repository = UnavailableAnalysisReportRepository(
        "analysis report repository is unavailable"
    )

    try:
        settings = get_settings()
    except ValidationError:
        settings = None

    if settings is not None:
        try:
            pool = open_connection_pool(create_connection_pool(settings))
        except Exception:
            app.state.analysis_report_repository = UnavailableAnalysisReportRepository(
                "analysis report repository is unavailable"
            )
        else:
            app.state.postgres_pool = pool
            app.state.analysis_report_repository = PostgreSQLAnalysisReportRepository(pool)

    yield

    pool = getattr(app.state, "postgres_pool", None)
    if pool is not None:
        close_connection_pool(pool)


def get_analysis_report_repository(request: Request) -> AnalysisReportRepository:
    return request.app.state.analysis_report_repository


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
    lifespan=lifespan,
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
async def create_analysis(
    request: AnalyzeRequest,
    repository: AnalysisReportRepository = Depends(get_analysis_report_repository),
) -> AnalysisResponse | JSONResponse:
    graph = build_analysis_graph(repository)

    try:
        result = graph.invoke({"request": request.model_dump(mode="python")})
        final_state = TradePilotState.model_validate(result)
    except RuntimeError as exc:
        if isinstance(exc.__cause__, RepositoryUnavailableError):
            return _build_error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="upstream_unavailable",
                message="analysis persistence is unavailable",
            )
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="analysis pipeline failed unexpectedly",
        )
    except Exception:
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="analysis pipeline failed unexpectedly",
        )

    if final_state.response is None:
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="analysis pipeline did not produce a response",
        )

    return final_state.response
