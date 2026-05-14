# stateful-agents

A small, crash-safe agent runtime in async Python. Every step a workflow takes
is checkpointed to an external state store (Redis, Postgres, SQLite, or a
no-op in-memory baseline). If the process dies mid-workflow, the next start
picks up at the exact step it was on — no replays, no lost work, no LangGraph.

```
┌──────────┐    save after every step    ┌────────────────┐
│ Worker   │ ──────────────────────────▶ │   StateStore   │
│ process  │                             │ (Redis/PG/…)   │
└──────────┘ ◀── load on (re)start ───── └────────────────┘
```

## Quickstart

```bash
cd python
uv venv && source .venv/bin/activate
uv pip install -e .

# 1. start Redis somewhere on :6379
docker run -d -p 6379:6379 redis:7

# 2. happy path
python -m demos.run_research --topic "How LLMs automate scientific research"

# 3. the demo: kill mid-workflow, then resume from Redis
python -m demos.crash_and_resume

# 4. benchmarks → benchmarks/results/*.png
python -m benchmarks.run_bench --suite all
python -m benchmarks.charts
```

## What's inside

| Module | What it does |
|---|---|
| `stateful_agents/state.py` | `AgentState` pydantic model — id, step, payload, fencing token. |
| `stateful_agents/engine.py` | `AgentEngine` with `@step("…")` decorator. `run()` is the loop: load → handler → save → repeat. |
| `stateful_agents/stores/` | Four backends behind a single `StateStore` protocol: Redis, Postgres, SQLite, in-memory. All save() paths reject stale writes by fencing token. |
| `stateful_agents/lock.py` | `DistributedLock` — `SET NX PX` acquire, atomic Lua release, background heartbeat task, monotonic fencing token via `INCR`. |
| `stateful_agents/workflows/research.py` | Sample 4-step research workflow ported from the original TS prototype. |
| `demos/crash_and_resume.py` | Spawns the workflow, `SIGKILL`s it mid-step, prints the surviving state, restarts. |
| `benchmarks/` | Latency, throughput, cold-resume suites + dark-themed charts. |

## Crash safety, in one sentence

`AgentEngine.run` saves `state` after every step before doing anything else.
A handler that returns is a step that is durably done. A handler that crashes
is a step that didn't happen — so on restart, we re-enter it with the same
input state.

For long-running steps (e.g. `FETCH_DATA`) we shard the loop: each invocation
handles one plan-section and bumps a `fetch_index`, so partial progress is also
durable.

## Distributed locking

Two workers running the same agent_id is a recipe for silent corruption
(see `docs/two_worker_race.mmd`). The fix:

1. **Mutual exclusion:** `SET lock:{agent_id} <uuid> NX PX <ttl>` before doing
   any work. Renew with a Lua `PEXPIRE` heartbeat every `ttl/3`.
2. **Fencing tokens:** `INCR fence:{agent_id}` returns a monotonically
   increasing integer per acquisition. Every `save()` carries that token.
3. **Server-side rejection:** the store refuses any write whose token is
   smaller than the persisted one. So even if a partitioned-but-alive worker
   finally reaches Redis with a stale token, its write is dropped — not
   silently committed. See `docs/fencing_timeline.mmd`.

## Benchmark results

All from a single MacBook Air (M-series), Redis 7 over local TCP, SQLite in
WAL mode. Re-runnable via `python -m benchmarks.run_bench`.

- `benchmarks/results/latency.png` — save+load latency by payload size (1KB → 1MB)
- `benchmarks/results/throughput.png` — ops/sec vs asyncio concurrency
- `benchmarks/results/cold_resume.png` — time from process start to first applied step

## Talk

This repo backs a talk at **PyDelhi, May 23 2026** on production-grade
stateful agents without an agent framework. Slides will be linked here after
the event.

## Repo layout

```
engine/                       original TS prototype (reference only)
python/
  stateful_agents/            engine, stores, lock, workflows
  demos/                      run_research.py, crash_and_resume.py
  benchmarks/                 run_bench.py, charts.py, results/
docs/                         mermaid diagrams (architecture, race, fencing)
```

## License

MIT.
