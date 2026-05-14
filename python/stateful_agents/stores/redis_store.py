from __future__ import annotations

import redis.asyncio as redis

from ..state import AgentState
from .base import StaleWriteError


_SAVE_LUA = """
local key = KEYS[1]
local incoming = tonumber(ARGV[1])
local payload = ARGV[2]
local ttl_s = tonumber(ARGV[3])
local existing = redis.call("get", key)
if existing then
    local cur = cjson.decode(existing)
    local cur_token = tonumber(cur["fencing_token"]) or 0
    if cur_token > incoming then
        return -1
    end
end
redis.call("set", key, payload, "EX", ttl_s)
return 1
"""


class RedisStateStore:
    """Redis-backed state store. Save is fencing-token aware via Lua CAS."""

    def __init__(
        self,
        client: redis.Redis,
        namespace: str = "agent:v1",
        ttl_seconds: int = 7 * 24 * 3600,
    ):
        self.r = client
        self.ns = namespace
        self.ttl_s = ttl_seconds
        self._save_script = self.r.register_script(_SAVE_LUA)

    def _key(self, agent_id: str) -> str:
        return f"{self.ns}:{agent_id}"

    async def save(self, state: AgentState) -> None:
        result = await self._save_script(
            keys=[self._key(state.agent_id)],
            args=[state.fencing_token, state.model_dump_json(), self.ttl_s],
        )
        if int(result) == -1:
            raise StaleWriteError(
                f"refused stale write for {state.agent_id}: token={state.fencing_token}"
            )

    async def load(self, agent_id: str) -> AgentState | None:
        raw = await self.r.get(self._key(agent_id))
        return AgentState.model_validate_json(raw) if raw else None

    async def delete(self, agent_id: str) -> None:
        await self.r.delete(self._key(agent_id))
