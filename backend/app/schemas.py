from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    country: Literal["ALL", "KR", "JP", "TW"] = "ALL"
