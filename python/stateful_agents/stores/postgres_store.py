from __future__ import annotations

import asyncpg

from ..state import AgentState
from .base import StaleWriteError


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id TEXT PRIMARY KEY,
    state JSONB NOT NULL,
    fencing_token BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_UPSERT = """
INSERT INTO agent_state (agent_id, state, fencing_token, updated_at)
VALUES ($1, $2::jsonb, $3, NOW())
ON CONFLICT (agent_id) DO UPDATE
SET state = EXCLUDED.state,
    fencing_token = EXCLUDED.fencing_token,
    updated_at = NOW()
WHERE agent_state.fencing_token <= EXCLUDED.fencing_token
RETURNING agent_id;
"""


class PostgresStateStore:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresStateStore":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
        async with pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        return cls(pool)

    async def save(self, state: AgentState) -> None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                _UPSERT, state.agent_id, state.model_dump_json(), state.fencing_token
            )
            if row is None:
                raise StaleWriteError(
                    f"refused stale write for {state.agent_id}: token={state.fencing_token}"
                )

    async def load(self, agent_id: str) -> AgentState | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM agent_state WHERE agent_id = $1", agent_id
            )
            return AgentState.model_validate_json(row["state"]) if row else None

    async def delete(self, agent_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_state WHERE agent_id = $1", agent_id)

    async def close(self) -> None:
        await self.pool.close()
