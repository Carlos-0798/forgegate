from __future__ import annotations

from typing import Literal

from pydantic import Field

from forgegate.domain.models import StrictModel


class ApiError(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    message: str = Field(min_length=1, max_length=1000)
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class ApiErrorResponse(StrictModel):
    error: ApiError


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    api_version: Literal["v1"] = "v1"
    forgegate_version: str = Field(min_length=1, max_length=120)
    store_schema: Literal["forgegate.candidate-store.v5"] = "forgegate.candidate-store.v5"


__all__ = ["ApiError", "ApiErrorResponse", "HealthResponse"]
