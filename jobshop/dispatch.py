"""Dispatching rules for the job shop, run in a simple discrete-event simulation.

Whenever a machine becomes free and at least one job is waiting for it, the
machine immediately starts the waiting job with the best (lowest) priority key.
The schedules this produces are "non-delay" schedules. Each rule is a function
returning a sort key; ties are broken by job index so results are deterministic.
"""

from __future__ import annotations

import numpy as np

from .instance import Instance


def _fifo(ctx):
    return (ctx["ready"], ctx["job"])


def _spt(ctx):
    return (ctx["duration"], ctx["ready"], ctx["job"])


def _edd(ctx):
    return (ctx["due"], ctx["ready"], ctx["job"])


def _mwkr(ctx):
    # Most work remaining first: negate so the largest remaining work has the lowest key.
    return (-ctx["remaining"], ctx["ready"], ctx["job"])


def _cr(ctx):
    # Critical ratio: time until the due date divided by remaining work. Smallest = most urgent.
    return ((ctx["due"] - ctx["now"]) / ctx["remaining"], ctx["ready"], ctx["job"])


RULES = {
    "FIFO": _fifo,   # first come, first served
    "SPT": _spt,     # shortest processing time of the next operation
    "EDD": _edd,     # earliest due date
    "MWKR": _mwkr,   # most work remaining
    "CR": _cr,       # critical ratio
}


def dispatch(inst: Instance, rule: str = "FIFO", seed: int = 0):
    """Simulate the shop under a dispatching rule. Returns ``starts[j][k]``.

    ``rule`` is one of ``RULES`` or ``"RANDOM"`` (a uniformly random waiting job, seeded).
    """
    rng = np.random.default_rng(seed)
    n, n_m = inst.n_jobs, inst.n_machines
    next_op = [0] * n
    ready = [0] * n                        # time at which job j can start its next operation
    remaining = [inst.total_work(j) for j in range(n)]
    machine_free = [0] * n_m
    starts = [[None] * len(r) for r in inst.routes]
    left = inst.n_ops
    now = 0

    while left > 0:
        for m in range(n_m):
            if machine_free[m] > now:
                continue
            waiting = [
                j for j in range(n)
                if next_op[j] < len(inst.routes[j])
                and inst.routes[j][next_op[j]][0] == m
                and ready[j] <= now
            ]
            if not waiting:
                continue
            if rule == "RANDOM":
                pick = waiting[int(rng.integers(len(waiting)))]
            else:
                key = RULES[rule]
                pick = min(
                    waiting,
                    key=lambda j: key(
                        {
                            "job": j,
                            "ready": ready[j],
                            "duration": inst.routes[j][next_op[j]][1],
                            "due": inst.due[j],
                            "remaining": remaining[j],
                            "now": now,
                        }
                    ),
                )
            k = next_op[pick]
            d = inst.routes[pick][k][1]
            starts[pick][k] = now
            machine_free[m] = now + d
            ready[pick] = now + d
            remaining[pick] -= d
            next_op[pick] += 1
            left -= 1

        # Jump to the next time something changes: a machine frees up or a job becomes ready.
        events = [t for t in machine_free if t > now]
        events += [ready[j] for j in range(n) if next_op[j] < len(inst.routes[j]) and ready[j] > now]
        if events:
            now = min(events)
        elif left > 0:
            raise RuntimeError("dispatch simulation stalled")  # cannot happen for valid instances

    return starts
