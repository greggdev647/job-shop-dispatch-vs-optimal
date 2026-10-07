"""Run every experiment and write tables and figures to results/.

    python run_experiments.py            # full run (a few minutes on 2 cores)
    python run_experiments.py --quick    # tiny smoke run
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from jobshop import RULES, dispatch, evaluate, ft06, random_instance, solve, validate

OUT = Path(__file__).parent / "results"
SIZES = [(6, 6), (10, 5), (10, 10)]          # (jobs, machines)
RULE_NAMES = list(RULES) + ["RANDOM"]
SIZE_COLORS = {"6x6": "#2a78d6", "10x5": "#eb6834", "10x10": "#1baf7a"}
INK, MUTED, GRID = "#1f2933", "#5f6b76", "#e3e7ea"


def run_one(args):
    """One instance: every rule plus CP-SAT for both objectives."""
    n_jobs, n_m, idx, time_limit = args
    rng = np.random.default_rng(1000 * n_jobs + 10 * n_m + idx)
    inst = random_instance(n_jobs, n_m, rng)
    cm = solve(inst, "makespan", time_limit=time_limit)
    ct = solve(inst, "total_tardiness", time_limit=time_limit)
    rows = []
    for rule in RULE_NAMES:
        m = evaluate(inst, dispatch(inst, rule, seed=0))
        rows.append(
            dict(size=f"{n_jobs}x{n_m}", instance=idx, rule=rule,
                 makespan=m["makespan"], total_tardiness=m["total_tardiness"],
                 cp_makespan=cm.objective, cp_makespan_bound=cm.bound, cp_makespan_optimal=cm.optimal,
                 cp_tardiness=ct.objective, cp_tardiness_bound=ct.bound, cp_tardiness_optimal=ct.optimal)
        )
    return rows


def style_axes(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (size, rule), g in df.groupby(["size", "rule"], sort=False):
        out.append(dict(
            size=size, rule=rule,
            makespan_gap_pct=100 * (g.makespan / g.cp_makespan - 1).mean(),
            tardiness_ratio=g.total_tardiness.sum() / max(g.cp_tardiness.sum(), 1),
        ))
    return pd.DataFrame(out)


def proof_rates(df: pd.DataFrame) -> pd.DataFrame:
    g = df.drop_duplicates(["size", "instance"]).groupby("size", sort=False)
    return pd.DataFrame({
        "instances": g.size(),
        "makespan_proven_optimal": g.cp_makespan_optimal.sum(),
        "tardiness_proven_optimal": g.cp_tardiness_optimal.sum(),
    }).reset_index()


def plot_gaps(summary: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    sizes = [f"{a}x{b}" for a, b in SIZES]
    w = 0.26
    x = np.arange(len(RULE_NAMES))
    for ax, col, title, ylab in [
        (axes[0], "makespan_gap_pct", "Makespan: mean gap above CP-SAT best", "gap (%)"),
        (axes[1], "tardiness_ratio", "Total tardiness: rule total / CP-SAT total", "ratio (1 = as good as CP-SAT)"),
    ]:
        for i, size in enumerate(sizes):
            vals = [summary[(summary["size"] == size) & (summary.rule == r)][col].iloc[0] for r in RULE_NAMES]
            ax.bar(x + (i - 1) * w, vals, w * 0.9, color=SIZE_COLORS[size], label=f"{size} (jobs x machines)",
                   edgecolor="none")
        ax.set_xticks(x)
        ax.set_xticklabels(RULE_NAMES)
        ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.set_ylabel(ylab, color=MUTED)
        style_axes(ax)
    axes[1].axhline(1, color=MUTED, linewidth=1)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, labelcolor=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "rule_gaps.png", dpi=160)
    plt.close(fig)


def gantt(ax, inst, starts, title, cmax):
    cmap = plt.get_cmap("tab10")
    for j, route in enumerate(inst.routes):
        for k, (m, d) in enumerate(route):
            ax.barh(m, d, left=starts[j][k], color=cmap(j % 10), edgecolor="white", linewidth=1.2, height=0.7)
            ax.text(starts[j][k] + d / 2, m, str(j), ha="center", va="center", color="white", fontsize=7)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_yticks(range(inst.n_machines))
    ax.set_yticklabels([f"M{m}" for m in range(inst.n_machines)])
    ax.set_xlim(0, cmax)
    ax.invert_yaxis()
    ax.tick_params(colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def plot_ft06():
    inst = ft06()
    opt = solve(inst, "makespan", time_limit=20)
    validate(inst, opt.starts)
    rows = [("optimal (CP-SAT)", opt.starts)]
    results = {}
    for rule in RULE_NAMES:
        s = dispatch(inst, rule, seed=0)
        results[rule] = evaluate(inst, s)["makespan"]
    best_rule = min((r for r in RULE_NAMES if r != "RANDOM"), key=lambda r: results[r])
    worst_rule = max((r for r in RULE_NAMES if r != "RANDOM"), key=lambda r: results[r])
    cmax = max(results.values()) + 2
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    gantt(axes[0], inst, opt.starts, f"CP-SAT optimal: makespan {int(opt.objective)}", cmax)
    gantt(axes[1], inst, dispatch(inst, best_rule), f"Best rule ({best_rule}): makespan {results[best_rule]}", cmax)
    gantt(axes[2], inst, dispatch(inst, worst_rule), f"Worst rule ({worst_rule}): makespan {results[worst_rule]}", cmax)
    axes[2].set_xlabel("time (numbers inside bars are job indices)", color=MUTED)
    fig.tight_layout()
    fig.savefig(OUT / "ft06_gantt.png", dpi=160)
    plt.close(fig)
    return opt.objective, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    n_inst, tl = (2, 1.0) if a.quick else (15, 5.0)
    OUT.mkdir(exist_ok=True)

    tasks = [(n, m, i, tl) for n, m in SIZES for i in range(n_inst)]
    with ProcessPoolExecutor(max_workers=2) as ex:
        rows = [r for chunk in ex.map(run_one, tasks) for r in chunk]
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "runs.csv", index=False)

    summary = summarise(df)
    summary.to_csv(OUT / "summary.csv", index=False)
    proofs = proof_rates(df)
    proofs.to_csv(OUT / "proof_rates.csv", index=False)
    plot_gaps(summary)
    ft_opt, ft_res = plot_ft06()

    with open(OUT / "run_log.txt", "w") as f:
        f.write(f"instances per size: {n_inst}, CP-SAT time limit per objective: {tl}s, 1 worker\n\n")
        f.write(summary.round(2).to_string(index=False) + "\n\n")
        f.write(proofs.to_string(index=False) + "\n\n")
        f.write(f"ft06 optimal makespan: {ft_opt}\nft06 rule makespans: {ft_res}\n")
    print((OUT / "run_log.txt").read_text())


if __name__ == "__main__":
    main()
