from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    agent_id: str
    step: str
    payload: dict[str, Any] = Field(default_factory=dict)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)
    version: int = 1
    fencing_token: int = 0
