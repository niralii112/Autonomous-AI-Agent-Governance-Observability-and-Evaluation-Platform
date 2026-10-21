"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.auth
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Credentials."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Login result."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    access_token: str
    token_type: Literal['bearer']
    expires_in: int
    user: UserResponse
