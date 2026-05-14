from __future__ import annotations

import time
from typing import Awaitable, Callable

from rich.console import Console

from .lock import DistributedLock
from .state import AgentState
from .stores.base import StateStore

console = Console()
StepHandler = Callable[[AgentState], Awaitable[AgentState]]


class AgentEngine:
    def __init__(self, store: StateStore):
        self.store = store
        self.handlers: dict[str, StepHandler] = {}

    def step(self, name: str):
        """Decorator: registers a coroutine as the handler for `name`."""

        def decorate(fn: StepHandler) -> StepHandler:
            self.handlers[name] = fn
            return fn

        return decorate

    async def run(
        self,
        agent_id: str,
        initial_step: str,
        initial_payload: dict,
        lock: DistributedLock | None = None,
    ) -> AgentState:
        if lock is not None:
            async with lock as token:
                return await self._run_loop(agent_id, initial_step, initial_payload, token)
        return await self._run_loop(agent_id, initial_step, initial_payload, fencing_token=0)

    async def _run_loop(
        self, agent_id: str, initial_step: str, initial_payload: dict, fencing_token: int
    ) -> AgentState:
        state = await self.store.load(agent_id) or AgentState(
            agent_id=agent_id,
            step=initial_step,
            payload=initial_payload,
        )
        if fencing_token:
            state.fencing_token = fencing_token
        await self.store.save(state)

        while state.step != "DONE":
            handler = self.handlers.get(state.step)
            if handler is None:
                raise ValueError(f"No handler for step: {state.step}")
            console.print(f"[cyan]➜[/cyan]  step={state.step}")
            state = await handler(state)
            state.updated_at = time.time()
            if fencing_token:
                state.fencing_token = fencing_token
            await self.store.save(state)

        console.print("[green]✓[/green] workflow complete")
        return state
