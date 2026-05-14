from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..state import AgentState


class StaleWriteError(Exception):
    """Raised when a save is rejected because its fencing_token is stale."""


@runtime_checkable
class StateStore(Protocol):
    async def save(self, state: AgentState) -> None: ...
    async def load(self, agent_id: str) -> AgentState | None: ...
    async def delete(self, agent_id: str) -> None: ...
