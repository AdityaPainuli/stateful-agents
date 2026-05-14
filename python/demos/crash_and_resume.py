from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import redis.asyncio as redis
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

PYTHON_DIR = Path(__file__).resolve().parent.parent


async def _spawn(agent_id: str, topic: str, slow: float) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "demos.run_research",
        "--agent-id",
        agent_id,
        "--topic",
        topic,
        "--slow",
        str(slow),
        cwd=str(PYTHON_DIR),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def _show_state(agent_id: str) -> None:
    client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    raw = await client.get(f"agent:v1:{agent_id}")
    await client.aclose()
    if raw is None:
        console.print(f"[red]no state in redis for {agent_id}[/red]")
        return
    pretty = json.dumps(json.loads(raw), indent=2)
    console.print(
        Panel(
            Syntax(pretty, "json", theme="monokai", line_numbers=False),
            title=f"redis: agent:v1:{agent_id}",
            border_style="green",
        )
    )


async def _wipe(agent_id: str) -> None:
    client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    await client.delete(f"agent:v1:{agent_id}")
    await client.aclose()


async def main(agent_id: str, topic: str, kill_after: float, slow: float, no_crash: bool) -> None:
    load_dotenv()
    await _wipe(agent_id)

    if no_crash:
        console.print(Panel.fit("happy path — no crash", border_style="cyan"))
        proc = await _spawn(agent_id, topic, slow)
        await proc.wait()
        return

    console.print(
        Panel.fit(
            f"[bold]Step 1.[/bold] Start the agent.\n"
            f"[bold]Step 2.[/bold] After {kill_after:.1f}s, SIGKILL it mid-step.\n"
            f"[bold]Step 3.[/bold] Show that state survived in Redis.\n"
            f"[bold]Step 4.[/bold] Restart with same agent_id — it picks up where it left off.",
            title="crash & resume demo",
            border_style="cyan",
        )
    )

    proc = await _spawn(agent_id, topic, slow)
    console.print(f"[cyan]▶ pid={proc.pid} running…[/cyan]")
    await asyncio.sleep(kill_after)

    console.print(
        Panel.fit(
            f"[bold white]💥 SIGKILL pid={proc.pid}[/bold white]",
            border_style="red",
            style="on red",
        )
    )
    proc.send_signal(signal.SIGKILL)
    await proc.wait()
    await asyncio.sleep(2)

    console.print(Panel.fit("[bold green]state survived in Redis ↓[/bold green]",
                            border_style="green"))
    await _show_state(agent_id)
    await asyncio.sleep(2)

    console.print(Panel.fit("[bold cyan]▶ restarting with same agent_id…[/bold cyan]",
                            border_style="cyan"))
    proc = await _spawn(agent_id, topic, slow)
    rc = await proc.wait()
    if rc == 0:
        console.print(Panel.fit("[bold green]✓ workflow resumed and completed[/bold green]",
                                border_style="green"))
    else:
        console.print(f"[red]subprocess exited with code {rc}[/red]")


def cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent-id", default="demo-001")
    p.add_argument("--topic", default="How LLM agents can automate scientific research")
    p.add_argument("--kill-after", type=float, default=10.0)
    p.add_argument("--slow", type=float, default=1.0,
                   help="per-step sleep so the crash lands inside a step")
    p.add_argument("--no-crash", action="store_true", help="happy path only (slide 9)")
    args = p.parse_args()
    asyncio.run(main(args.agent_id, args.topic, args.kill_after, args.slow, args.no_crash))


if __name__ == "__main__":
    cli()
