from __future__ import annotations

import asyncio

from ..state import AgentState
from .base import StaleWriteError


class MemoryStateStore:
    """No-persistence control store. Used as the baseline in benchmarks."""

    def __init__(self):
        self._data: dict[str, AgentState] = {}
        self._lock = asyncio.Lock()

    async def save(self, state: AgentState) -> None:
        async with self._lock:
            existing = self._data.get(state.agent_id)
            if existing and existing.fencing_token > state.fencing_token:
                raise StaleWriteError(
                    f"refused stale write for {state.agent_id}: token={state.fencing_token}"
                )
            self._data[state.agent_id] = state.model_copy(deep=True)

    async def load(self, agent_id: str) -> AgentState | None:
        async with self._lock:
            s = self._data.get(agent_id)
            return s.model_copy(deep=True) if s else None

    async def delete(self, agent_id: str) -> None:
        async with self._lock:
            self._data.pop(agent_id, None)
