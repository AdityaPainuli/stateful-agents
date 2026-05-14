from __future__ import annotations

import asyncio
import uuid

import redis.asyncio as redis
from rich.console import Console

console = Console()


class LockUnavailable(Exception):
    """Raised when the lock cannot be acquired (already held by someone else)."""


_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class DistributedLock:
    """Async-context-manager Redis lock with fencing token + heartbeat.

    Usage:
        async with DistributedLock(redis_client, agent_id, ttl_ms=30_000) as token:
            ...   # token is monotonically increasing per agent_id

    Stores reject writes whose fencing_token is older than what's persisted,
    which prevents split-brain corruption when the lock TTL expires under a
    network partition.
    """

    def __init__(
        self,
        client: redis.Redis,
        agent_id: str,
        ttl_ms: int = 30_000,
        namespace: str = "agent:v1",
    ):
        self.r = client
        self.agent_id = agent_id
        self.ttl_ms = ttl_ms
        self.lock_key = f"{namespace}:lock:{agent_id}"
        self.fence_key = f"{namespace}:fence:{agent_id}"
        self.token_value = uuid.uuid4().hex
        self.fencing_token: int = 0
        self._heartbeat_task: asyncio.Task | None = None
        self._release_script = self.r.register_script(_RELEASE_LUA)
        self._renew_script = self.r.register_script(_RENEW_LUA)

    async def __aenter__(self) -> int:
        ok = await self.r.set(self.lock_key, self.token_value, nx=True, px=self.ttl_ms)
        if not ok:
            raise LockUnavailable(f"lock already held for {self.agent_id}")
        self.fencing_token = int(await self.r.incr(self.fence_key))
        console.print(
            f"[magenta]🔒 lock acquired[/magenta] agent={self.agent_id} "
            f"token={self.fencing_token}"
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        return self.fencing_token

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass
        released = await self._release_script(keys=[self.lock_key], args=[self.token_value])
        if int(released) == 1:
            console.print(f"[magenta]🔓 lock released[/magenta] agent={self.agent_id}")
        else:
            console.print(
                f"[red]⚠ lock lost before release[/red] agent={self.agent_id} "
                "(TTL expired or stolen)"
            )

    async def _heartbeat(self) -> None:
        interval = max(self.ttl_ms / 3 / 1000, 0.05)
        try:
            while True:
                await asyncio.sleep(interval)
                renewed = await self._renew_script(
                    keys=[self.lock_key], args=[self.token_value, self.ttl_ms]
                )
                if int(renewed) == 0:
                    console.print(
                        f"[red]⚠ heartbeat failed[/red] agent={self.agent_id} "
                        "— lock no longer ours"
                    )
                    return
        except asyncio.CancelledError:
            return
