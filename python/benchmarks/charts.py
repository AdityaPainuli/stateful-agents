from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"

COLORS = {
    "redis": "#22d3ee",
    "postgres": "#a78bfa",
    "sqlite": "#f59e0b",
    "memory": "#6b7280",
}
STORE_ORDER = ("redis", "postgres", "sqlite", "memory")

plt.rcParams.update(
    {
        "figure.facecolor": "#0d1117",
        "axes.facecolor": "#0d1117",
        "axes.edgecolor": "#30363d",
        "axes.labelcolor": "#e6edf3",
        "axes.titlecolor": "#e6edf3",
        "xtick.color": "#e6edf3",
        "ytick.color": "#e6edf3",
        "grid.color": "#21262d",
        "text.color": "#e6edf3",
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "DejaVu Sans"],
        "font.size": 13,
        "axes.titlesize": 16,
        "axes.labelsize": 14,
        "legend.fontsize": 12,
        "figure.figsize": (12, 6.75),
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.facecolor": "#0d1117",
    }
)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def _meta_caption(csv_name: str) -> str:
    meta_path = RESULTS / "meta.json"
    if not meta_path.exists():
        return ""
    meta = json.loads(meta_path.read_text()).get(csv_name, {})
    return (
        f"benchmark: {csv_name}, n={meta.get('n', '?')}, "
        f"hardware={meta.get('host', '?')} ({meta.get('platform', '?')})"
    )


def _add_caption(fig, text: str) -> None:
    fig.text(
        0.5, 0.005, text, ha="center", va="bottom", color="#6b7280", fontsize=10,
    )


def _stores_present(rows: list[dict]) -> list[str]:
    seen = {r["store"] for r in rows}
    return [s for s in STORE_ORDER if s in seen]


# ───────────────────────────── latency ─────────────────────────────


def chart_latency() -> None:
    rows = _read_csv(RESULTS / "latency.csv")
    if not rows:
        print("latency.csv missing — skipping")
        return
    sizes = sorted({int(r["state_size_kb"]) for r in rows})
    stores = _stores_present(rows)

    fig, ax = plt.subplots()
    n_stores = len(stores)
    group_width = 0.8
    bar_width = group_width / n_stores
    x = np.arange(len(sizes))

    by_store: dict[str, dict[int, dict[str, float]]] = {}
    for r in rows:
        by_store.setdefault(r["store"], {})[int(r["state_size_kb"])] = {
            "p50": float(r["p50_us"]),
            "p95": float(r["p95_us"]),
            "p99": float(r["p99_us"]),
        }

    for i, store in enumerate(stores):
        c = COLORS[store]
        offset = (i - (n_stores - 1) / 2) * bar_width
        p50 = [by_store[store][s]["p50"] for s in sizes]
        p95 = [by_store[store][s]["p95"] for s in sizes]
        p99 = [by_store[store][s]["p99"] for s in sizes]
        ax.bar(x + offset, p99, bar_width, color=c, alpha=0.45, label=f"{store} p99")
        ax.bar(x + offset, p95, bar_width, color=c, alpha=0.7, label=f"{store} p95")
        ax.bar(x + offset, p50, bar_width, color=c, alpha=1.0, label=f"{store} p50")

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s} KB" for s in sizes])
    ax.set_xlabel("state size")
    ax.set_ylabel("save+load latency (μs, log scale)")
    ax.set_title("State store latency by payload size")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(ncol=len(stores), loc="upper left", framealpha=0.0)

    _add_caption(fig, _meta_caption("latency.csv"))
    fig.savefig(RESULTS / "latency.png")
    plt.close(fig)
    print(f"wrote {RESULTS / 'latency.png'}")


# ───────────────────────────── throughput ─────────────────────────────


def chart_throughput() -> None:
    rows = _read_csv(RESULTS / "throughput.csv")
    if not rows:
        print("throughput.csv missing — skipping")
        return
    stores = _stores_present(rows)
    fig, ax = plt.subplots()
    by_store: dict[str, list[tuple[int, float]]] = {}
    for r in rows:
        by_store.setdefault(r["store"], []).append(
            (int(r["concurrency"]), float(r["ops_per_sec"]))
        )
    for store in stores:
        pts = sorted(by_store[store])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker="o", linewidth=2.5, markersize=9,
                color=COLORS[store], label=store)

    ax.set_xscale("log")
    ax.set_xlabel("concurrency (asyncio tasks)")
    ax.set_ylabel("ops / second")
    ax.set_title("State store throughput vs concurrency")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(framealpha=0.0)

    _add_caption(fig, _meta_caption("throughput.csv"))
    fig.savefig(RESULTS / "throughput.png")
    plt.close(fig)
    print(f"wrote {RESULTS / 'throughput.png'}")


# ───────────────────────────── cold-resume ─────────────────────────────


def chart_cold_resume() -> None:
    rows = _read_csv(RESULTS / "cold_resume.csv")
    if not rows:
        print("cold_resume.csv missing — skipping")
        return
    stores = _stores_present(rows)
    by_store = {r["store"]: r for r in rows}

    fig, ax = plt.subplots()
    means = [float(by_store[s]["mean_ms"]) for s in stores]
    stdevs = [float(by_store[s]["stdev_ms"]) for s in stores]
    colors = [COLORS[s] for s in stores]
    y = np.arange(len(stores))
    ax.barh(y, means, xerr=stdevs, color=colors, edgecolor="#0d1117",
            error_kw={"ecolor": "#e6edf3", "capsize": 6, "linewidth": 1.5})
    ax.set_yticks(y)
    ax.set_yticklabels(stores)
    ax.invert_yaxis()
    ax.set_xlabel("cold-resume time (ms, lower is better)")
    ax.set_title("Cold-resume: load state + apply one step")
    ax.grid(True, axis="x", alpha=0.3)

    for i, (m, s) in enumerate(zip(means, stdevs)):
        ax.text(m + s + max(means) * 0.01, i, f"{m:.2f} ± {s:.2f} ms",
                va="center", color="#e6edf3", fontsize=11)

    _add_caption(fig, _meta_caption("cold_resume.csv"))
    fig.savefig(RESULTS / "cold_resume.png")
    plt.close(fig)
    print(f"wrote {RESULTS / 'cold_resume.png'}")


def main() -> None:
    chart_latency()
    chart_throughput()
    chart_cold_resume()


if __name__ == "__main__":
    main()
