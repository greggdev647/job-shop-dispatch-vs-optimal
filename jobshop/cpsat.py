"""Exact / near-exact job-shop solver using Google OR-Tools CP-SAT.

Model: one interval variable per operation; "no overlap" on every machine;
precedence constraints along each job. Objective is either the makespan
(time the last job finishes) or the total tardiness (sum over jobs of the time
finished after the due date).
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .instance import Instance


@dataclass
class Solution:
    starts: list           # starts[j][k]
    objective: float       # best objective value found
    bound: float           # proven lower bound on the optimum
    status: str            # "OPTIMAL" or "FEASIBLE" (time limit hit)

    @property
    def optimal(self) -> bool:
        return self.status == "OPTIMAL"


def solve(
    inst: Instance,
    objective: str = "makespan",
    time_limit: float = 10.0,
    workers: int = 1,
    seed: int = 0,
) -> Solution:
    if objective not in ("makespan", "total_tardiness"):
        raise ValueError(f"unknown objective: {objective!r}")

    horizon = sum(d for r in inst.routes for _, d in r)
    model = cp_model.CpModel()

    starts, ends = [], []
    by_machine = [[] for _ in range(inst.n_machines)]
    for j, route in enumerate(inst.routes):
        s_row, e_row = [], []
        for k, (m, d) in enumerate(route):
            s = model.new_int_var(0, horizon, f"s_{j}_{k}")
            e = model.new_int_var(0, horizon, f"e_{j}_{k}")
            iv = model.new_interval_var(s, d, e, f"iv_{j}_{k}")
            by_machine[m].append(iv)
            s_row.append(s)
            e_row.append(e)
        for k in range(len(route) - 1):
            model.add(s_row[k + 1] >= e_row[k])
        starts.append(s_row)
        ends.append(e_row)

    for intervals in by_machine:
        model.add_no_overlap(intervals)

    finish = [row[-1] for row in ends]
    if objective == "makespan":
        cmax = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(cmax, finish)
        model.minimize(cmax)
    else:
        tard = []
        for j, f in enumerate(finish):
            t = model.new_int_var(0, horizon, f"tard_{j}")
            model.add(t >= f - inst.due[j])
            tard.append(t)
        model.minimize(sum(tard))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT found no schedule (status {solver.status_name(status)})")

    return Solution(
        starts=[[solver.value(s) for s in row] for row in starts],
        objective=solver.objective_value,
        bound=solver.best_objective_bound,
        status=solver.status_name(status),
    )
