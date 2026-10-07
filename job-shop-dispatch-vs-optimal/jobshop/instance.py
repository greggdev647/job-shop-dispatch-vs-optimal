"""Job-shop instances.

A job shop has ``n_machines`` machines and ``n_jobs`` jobs. Each job is a fixed
sequence of operations; each operation needs one specific machine for a given
number of time units. A machine does one operation at a time, an operation
cannot start before the previous operation of the same job has finished, and
operations cannot be interrupted. All jobs are available at time 0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Instance:
    routes: tuple          # routes[j] = ((machine, duration), (machine, duration), ...)
    due: tuple             # due[j] = due date of job j
    n_machines: int

    @property
    def n_jobs(self) -> int:
        return len(self.routes)

    @property
    def n_ops(self) -> int:
        return sum(len(r) for r in self.routes)

    def total_work(self, j: int) -> int:
        return sum(d for _, d in self.routes[j])


def random_instance(
    n_jobs: int,
    n_machines: int,
    rng: np.random.Generator,
    duration_range: tuple = (1, 20),
    due_factor: float = 1.5,
) -> Instance:
    """Random instance in which every job visits every machine exactly once, in random order.

    Durations are uniform integers in ``duration_range``. The due date of a job is
    ``ceil(due_factor * total processing time of the job)`` (the "total work content" rule).
    """
    lo, hi = duration_range
    routes, due = [], []
    for _ in range(n_jobs):
        order = rng.permutation(n_machines)
        durations = rng.integers(lo, hi + 1, size=n_machines)
        route = tuple((int(m), int(d)) for m, d in zip(order, durations))
        routes.append(route)
        due.append(int(np.ceil(due_factor * sum(d for _, d in route))))
    return Instance(routes=tuple(routes), due=tuple(due), n_machines=n_machines)


def ft06() -> Instance:
    """The classic 6x6 benchmark of Fisher and Thompson (1963). Its optimal makespan is 55."""
    raw = [
        [(2, 1), (0, 3), (1, 6), (3, 7), (5, 3), (4, 6)],
        [(1, 8), (2, 5), (4, 10), (5, 10), (0, 10), (3, 4)],
        [(2, 5), (3, 4), (5, 8), (0, 9), (1, 1), (4, 7)],
        [(1, 5), (0, 5), (2, 5), (3, 3), (4, 8), (5, 9)],
        [(2, 9), (1, 3), (4, 5), (5, 4), (0, 3), (3, 1)],
        [(1, 3), (3, 3), (5, 9), (0, 10), (4, 4), (2, 1)],
    ]
    routes = tuple(tuple(r) for r in raw)
    due = tuple(int(np.ceil(1.5 * sum(d for _, d in r))) for r in routes)
    return Instance(routes=routes, due=due, n_machines=6)
