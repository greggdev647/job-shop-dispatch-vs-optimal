"""Schedules: validation and objective values.

A schedule is ``starts[j][k]`` = start time of operation k of job j.
"""

from __future__ import annotations

from .instance import Instance


def validate(inst: Instance, starts) -> None:
    """Raise ``AssertionError`` if the schedule breaks any job-shop rule."""
    # Every operation is scheduled, at a non-negative time.
    assert len(starts) == inst.n_jobs, "one start list per job"
    for j, route in enumerate(inst.routes):
        assert len(starts[j]) == len(route), f"job {j}: wrong number of operations"
        for k in range(len(route)):
            assert starts[j][k] >= 0, f"job {j} op {k}: negative start"

    # Operations of one job run in order and do not overlap.
    for j, route in enumerate(inst.routes):
        for k in range(len(route) - 1):
            end_k = starts[j][k] + route[k][1]
            assert starts[j][k + 1] >= end_k, f"job {j}: op {k + 1} starts before op {k} ends"

    # A machine does one operation at a time.
    per_machine = [[] for _ in range(inst.n_machines)]
    for j, route in enumerate(inst.routes):
        for k, (m, d) in enumerate(route):
            per_machine[m].append((starts[j][k], starts[j][k] + d, j, k))
    for m, ops in enumerate(per_machine):
        ops.sort()
        for (s1, e1, j1, k1), (s2, e2, j2, k2) in zip(ops, ops[1:]):
            assert s2 >= e1, f"machine {m}: job {j1} op {k1} overlaps job {j2} op {k2}"


def completion_times(inst: Instance, starts) -> list:
    return [starts[j][-1] + inst.routes[j][-1][1] for j in range(inst.n_jobs)]


def makespan(inst: Instance, starts) -> int:
    return max(completion_times(inst, starts))


def total_tardiness(inst: Instance, starts) -> int:
    return sum(max(0, c - d) for c, d in zip(completion_times(inst, starts), inst.due))


def evaluate(inst: Instance, starts) -> dict:
    validate(inst, starts)
    return {"makespan": makespan(inst, starts), "total_tardiness": total_tardiness(inst, starts)}
