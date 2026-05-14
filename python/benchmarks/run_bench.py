from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import platform
import secrets
import socket
import statistics
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from stateful_agents.state import AgentState
from stateful_agents.stores.base import StateStore

from ._stores import STORES, open_store

console = Console()
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True, parents=True)

LATENCY_SIZES_KB = (1, 10, 100, 1000)
THROUGHPUT_CONCURRENCY = (1, 10, 50, 200)
LATENCY_OPS = 1000
THROUGHPUT_DURATION_S = 10
COLD_RESUME_AGENTS = 100
COLD_RESUME_TRIALS = 20


def _make_state(size_kb: int, agent_id: str | None = None) -> AgentState:
    blob = secrets.token_hex(size_kb * 512)  # hex doubles → ~size_kb*1024 bytes
    return AgentState(
        agent_id=agent_id or f"bench-{secrets.token_hex(4)}",
        step="STEP",
        payload={"blob": blob},
    )


async def _warmup(store: StateStore, n: int = 100) -> None:
    s = _make_state(1)
    for _ in range(n):
        await store.save(s)
        await store.load(s.agent_id)
    await store.delete(s.agent_id)


# ───────────────────────────── latency ─────────────────────────────


async def _bench_latency_one(
    store: StateStore, size_kb: int, ops: int
) -> tuple[float, float, float]:
    state = _make_state(size_kb)
    await store.save(state)
    await _warmup(store)
    samples: list[float] = []
    for _ in range(ops):
        t0 = time.perf_counter_ns()
        await store.save(state)
        await store.load(state.agent_id)
        samples.append((time.perf_counter_ns() - t0) / 1000.0)  # → microseconds
    await store.delete(state.agent_id)
    samples.sort()
    p = lambda q: samples[min(len(samples) - 1, int(len(samples) * q))]
    return p(0.50), p(0.95), p(0.99)


async def bench_latency(stores: tuple[str, ...]) -> None:
    rows: list[dict] = []
    with Progress(
        TextColumn("[bold]latency[/bold]"),
        BarColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        total = len(stores) * len(LATENCY_SIZES_KB)
        task = prog.add_task("…", total=total)
        for store_name in stores:
            try:
                async with open_store(store_name) as store:
                    for kb in LATENCY_SIZES_KB:
                        prog.update(task, description=f"{store_name} @ {kb}KB")
                        p50, p95, p99 = await _bench_latency_one(store, kb, LATENCY_OPS)
                        rows.append(
                            {
                                "store": store_name,
                                "state_size_kb": kb,
                                "p50_us": round(p50, 2),
                                "p95_us": round(p95, 2),
                                "p99_us": round(p99, 2),
                            }
                        )
                        prog.advance(task)
            except Exception as e:
                console.print(f"[red]skip {store_name}: {e}[/red]")
                prog.advance(task, advance=len(LATENCY_SIZES_KB))
    _write_csv(RESULTS / "latency.csv",
               ["store", "state_size_kb", "p50_us", "p95_us", "p99_us"], rows)
    _write_meta("latency.csv", n=LATENCY_OPS, extra={"sizes_kb": list(LATENCY_SIZES_KB)})


# ───────────────────────────── throughput ─────────────────────────────


async def _throughput_worker(store: StateStore, agent_id: str, deadline: float) -> int:
    state = _make_state(10, agent_id=agent_id)
    await store.save(state)
    n = 0
    while time.perf_counter() < deadline:
        await store.save(state)
        await store.load(agent_id)
        n += 1
    return n


async def _bench_throughput_one(store: StateStore, concurrency: int) -> float:
    deadline = time.perf_counter() + THROUGHPUT_DURATION_S
    tasks = [
        asyncio.create_task(_throughput_worker(store, f"thr-{i}-{secrets.token_hex(2)}", deadline))
        for i in range(concurrency)
    ]
    counts = await asyncio.gather(*tasks)
    return sum(counts) / THROUGHPUT_DURATION_S


async def bench_throughput(stores: tuple[str, ...]) -> None:
    rows: list[dict] = []
    with Progress(
        TextColumn("[bold]throughput[/bold]"),
        BarColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        total = len(stores) * len(THROUGHPUT_CONCURRENCY)
        task = prog.add_task("…", total=total)
        for store_name in stores:
            try:
                async with open_store(store_name) as store:
                    await _warmup(store)
                    for c in THROUGHPUT_CONCURRENCY:
                        prog.update(task, description=f"{store_name} @ c={c}")
                        ops = await _bench_throughput_one(store, c)
                        rows.append(
                            {
                                "store": store_name,
                                "concurrency": c,
                                "ops_per_sec": round(ops, 2),
                            }
                        )
                        prog.advance(task)
            except Exception as e:
                console.print(f"[red]skip {store_name}: {e}[/red]")
                prog.advance(task, advance=len(THROUGHPUT_CONCURRENCY))
    _write_csv(RESULTS / "throughput.csv",
               ["store", "concurrency", "ops_per_sec"], rows)
    _write_meta("throughput.csv", n=THROUGHPUT_DURATION_S,
                extra={"concurrency": list(THROUGHPUT_CONCURRENCY), "duration_s": THROUGHPUT_DURATION_S})


# ───────────────────────────── cold-resume ─────────────────────────────


async def _seed_agents(store: StateStore, n: int) -> list[str]:
    steps = ["GENERATE_QUESTIONS", "GENERATE_PLAN", "FETCH_DATA", "GENERATE_REPORT"]
    ids: list[str] = []
    for i in range(n):
        s = _make_state(10, agent_id=f"cold-{i}")
        s.step = steps[i % len(steps)]
        await store.save(s)
        ids.append(s.agent_id)
    return ids


async def _cold_resume_trial(store: StateStore, ids: list[str]) -> float:
    """Simulate process startup: time from first load() to first save()."""
    target = ids[0]
    t0 = time.perf_counter_ns()
    state = await store.load(target)
    if state is None:
        raise RuntimeError("missing seeded agent")
    state.payload["resumed"] = True
    await store.save(state)
    return (time.perf_counter_ns() - t0) / 1_000_000.0  # → ms


async def bench_cold_resume(stores: tuple[str, ...]) -> None:
    rows: list[dict] = []
    with Progress(
        TextColumn("[bold]cold-resume[/bold]"),
        BarColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("…", total=len(stores))
        for store_name in stores:
            prog.update(task, description=store_name)
            try:
                async with open_store(store_name) as store:
                    ids = await _seed_agents(store, COLD_RESUME_AGENTS)
                    samples = []
                    for _ in range(COLD_RESUME_TRIALS):
                        samples.append(await _cold_resume_trial(store, ids))
                    rows.append(
                        {
                            "store": store_name,
                            "mean_ms": round(statistics.mean(samples), 3),
                            "stdev_ms": round(
                                statistics.stdev(samples) if len(samples) > 1 else 0.0, 3
                            ),
                        }
                    )
            except Exception as e:
                console.print(f"[red]skip {store_name}: {e}[/red]")
            prog.advance(task)
    _write_csv(RESULTS / "cold_resume.csv", ["store", "mean_ms", "stdev_ms"], rows)
    _write_meta("cold_resume.csv", n=COLD_RESUME_TRIALS,
                extra={"agents": COLD_RESUME_AGENTS})


# ───────────────────────────── helpers ─────────────────────────────


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    console.print(f"[green]wrote[/green] {path}")


def _write_meta(csv_name: str, n: int, extra: dict | None = None) -> None:
    meta_path = RESULTS / "meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    meta[csv_name] = {
        "n": n,
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        **(extra or {}),
    }
    meta_path.write_text(json.dumps(meta, indent=2))


def cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=("latency", "throughput", "cold_resume", "all"),
                   default="all")
    p.add_argument("--stores", default=",".join(STORES),
                   help="comma-separated subset of stores to bench")
    args = p.parse_args()
    stores = tuple(s.strip() for s in args.stores.split(",") if s.strip())

    async def _run():
        if args.suite in ("latency", "all"):
            await bench_latency(stores)
        if args.suite in ("throughput", "all"):
            await bench_throughput(stores)
        if args.suite in ("cold_resume", "all"):
            await bench_cold_resume(stores)

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
