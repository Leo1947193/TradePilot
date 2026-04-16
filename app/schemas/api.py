from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


Ticker = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason: str


class ErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorObject
