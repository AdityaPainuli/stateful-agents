"""Helpers for spinning up each store with a clean namespace."""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import redis.asyncio as redis

from stateful_agents.stores.base import StateStore
from stateful_agents.stores.memory_store import MemoryStateStore
from stateful_agents.stores.redis_store import RedisStateStore

STORES = ("redis", "postgres", "sqlite", "memory")


@asynccontextmanager
async def open_store(name: str) -> AsyncIterator[StateStore]:
    if name == "memory":
        yield MemoryStateStore()
        return

    if name == "redis":
        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        ns = f"bench:{secrets.token_hex(4)}"
        try:
            yield RedisStateStore(client, namespace=ns)
        finally:
            keys = await client.keys(f"{ns}:*")
            if keys:
                await client.delete(*keys)
            await client.aclose()
        return

    if name == "sqlite":
        from stateful_agents.stores.sqlite_store import SqliteStateStore

        path = Path(f"/tmp/stateful-bench-{secrets.token_hex(4)}.sqlite")
        store = await SqliteStateStore.connect(str(path))
        try:
            yield store
        finally:
            await store.close()
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return

    if name == "postgres":
        from stateful_agents.stores.postgres_store import PostgresStateStore

        dsn = os.environ.get("POSTGRES_DSN", "postgresql://postgres@localhost:5432/postgres")
        store = await PostgresStateStore.connect(dsn)
        try:
            yield store
        finally:
            await store.close()
        return

    raise ValueError(f"unknown store: {name}")
