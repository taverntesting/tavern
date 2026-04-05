"""Pydantic models for HTTP example responses."""

from pydantic import BaseModel, ConfigDict


class HelloResponse(BaseModel):
    """Response model for /hello/<name> endpoint."""

    data: str


class PingResponse(BaseModel):
    """Response model for /ping endpoint."""

    data: str


class StrictPingResponse(BaseModel):
    """Response model for /ping endpoint that rejects extra fields."""

    model_config = ConfigDict(extra="forbid")
    data: str


class NumberResponse(BaseModel):
    """Response model for /numbers endpoint."""

    number: int


class LoginResponse(BaseModel):
    """Response model for /login endpoint."""

    token: str


class ErrorResponse(BaseModel):
    """Response model for error responses."""

    error: str
