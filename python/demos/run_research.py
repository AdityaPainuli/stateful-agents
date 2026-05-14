from __future__ import annotations

import argparse
import asyncio
import os

import redis.asyncio as redis
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from stateful_agents.stores.redis_store import RedisStateStore
from stateful_agents.workflows.research import build_research_agent

console = Console()


async def main(agent_id: str, topic: str, slow: float) -> None:
    load_dotenv()
    client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    store = RedisStateStore(client)
    agent = build_research_agent(store)

    if slow > 0:
        # Wrap each handler in a sleep so the crash demo has time to interrupt.
        original = dict(agent.handlers)

        for name, fn in original.items():
            async def slow_step(state, _fn=fn):
                await asyncio.sleep(slow)
                return await _fn(state)

            agent.handlers[name] = slow_step

    console.print(
        Panel.fit(
            f"[bold cyan]agent_id[/bold cyan] = {agent_id}\n"
            f"[bold cyan]topic[/bold cyan]    = {topic}",
            title="research workflow",
            border_style="cyan",
        )
    )
    await agent.run(agent_id, "GENERATE_QUESTIONS", {"topic": topic})
    await client.aclose()


def cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent-id", default="demo-001")
    p.add_argument("--topic", default="How LLM agents can automate scientific research")
    p.add_argument(
        "--slow",
        type=float,
        default=0.0,
        help="seconds to sleep before each step (used by crash demo for timing)",
    )
    args = p.parse_args()
    asyncio.run(main(args.agent_id, args.topic, args.slow))


if __name__ == "__main__":
    cli()
