from __future__ import annotations

import aiosqlite

from ..state import AgentState
from .base import StaleWriteError


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    fencing_token INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);
"""


class SqliteStateStore:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    @classmethod
    async def connect(cls, path: str) -> "SqliteStateStore":
        db = await aiosqlite.connect(path)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute(_SCHEMA)
        await db.commit()
        return cls(db)

    async def save(self, state: AgentState) -> None:
        import time

        cursor = await self.db.execute(
            """
            INSERT INTO agent_state (agent_id, state, fencing_token, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                state = excluded.state,
                fencing_token = excluded.fencing_token,
                updated_at = excluded.updated_at
            WHERE agent_state.fencing_token <= excluded.fencing_token
            """,
            (state.agent_id, state.model_dump_json(), state.fencing_token, time.time()),
        )
        await self.db.commit()
        if cursor.rowcount == 0:
            raise StaleWriteError(
                f"refused stale write for {state.agent_id}: token={state.fencing_token}"
            )

    async def load(self, agent_id: str) -> AgentState | None:
        async with self.db.execute(
            "SELECT state FROM agent_state WHERE agent_id = ?", (agent_id,)
        ) as cur:
            row = await cur.fetchone()
        return AgentState.model_validate_json(row[0]) if row else None

    async def delete(self, agent_id: str) -> None:
        await self.db.execute("DELETE FROM agent_state WHERE agent_id = ?", (agent_id,))
        await self.db.commit()

    async def close(self) -> None:
        await self.db.close()
