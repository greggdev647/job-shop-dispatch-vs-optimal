import numpy as np
import pytest

from jobshop import (
    RULES,
    Instance,
    dispatch,
    evaluate,
    ft06,
    makespan,
    random_instance,
    solve,
    total_tardiness,
    validate,
)

ALL_RULES = list(RULES) + ["RANDOM"]


def tiny() -> Instance:
    """Two jobs, two machines. Worked by hand in the comments of the tests below."""
    return Instance(
        routes=(((0, 3), (1, 2)), ((1, 2), (0, 3))),
        due=(5, 5),
        n_machines=2,
    )


def test_random_instance_shape_and_determinism():
    a = random_instance(7, 4, np.random.default_rng(1))
    b = random_instance(7, 4, np.random.default_rng(1))
    assert a == b
    assert a.n_jobs == 7 and a.n_machines == 4 and a.n_ops == 28
    for route in a.routes:
        assert sorted(m for m, _ in route) == [0, 1, 2, 3]       # each machine exactly once
        assert all(1 <= d <= 20 for _, d in route)


def test_fifo_on_the_tiny_instance_matches_hand_calculation():
    # t=0: machine 0 starts job 0 (3 units), machine 1 starts job 1 (2 units).
    # t=3: machine 0 is free and job 1 is ready -> job 1 op 1 runs 3..6;
    #      machine 1 is free and job 0 is ready -> job 0 op 1 runs 3..5.
    starts = dispatch(tiny(), "FIFO")
    assert starts == [[0, 3], [0, 3]]
    assert makespan(tiny(), starts) == 6
    assert total_tardiness(tiny(), starts) == 1          # job 1 finishes at 6, due 5


def test_cpsat_on_the_tiny_instance():
    inst = tiny()
    best_makespan = solve(inst, "makespan")
    best_tardiness = solve(inst, "total_tardiness")
    assert best_makespan.optimal and best_makespan.objective == 6
    assert best_tardiness.optimal and best_tardiness.objective == 1


def test_cpsat_reproduces_the_known_ft06_optimum():
    sol = solve(ft06(), "makespan", time_limit=20)
    assert sol.optimal
    assert sol.objective == 55
    validate(ft06(), sol.starts)


@pytest.mark.parametrize("rule", ALL_RULES)
def test_every_rule_produces_a_valid_schedule(rule):
    rng = np.random.default_rng(3)
    for _ in range(10):
        inst = random_instance(8, 5, rng)
        validate(inst, dispatch(inst, rule, seed=1))


def test_random_rule_is_reproducible_for_a_seed():
    inst = random_instance(8, 5, np.random.default_rng(5))
    assert dispatch(inst, "RANDOM", seed=2) == dispatch(inst, "RANDOM", seed=2)


def test_solver_is_never_worse_than_any_dispatching_rule():
    rng = np.random.default_rng(11)
    for _ in range(4):
        inst = random_instance(6, 4, rng)
        cm = solve(inst, "makespan", time_limit=10)
        ct = solve(inst, "total_tardiness", time_limit=10)
        assert cm.optimal and ct.optimal
        for rule in ALL_RULES:
            m = evaluate(inst, dispatch(inst, rule, seed=0))
            assert cm.objective <= m["makespan"]
            assert ct.objective <= m["total_tardiness"]


def test_validator_catches_overlap_and_precedence_violations():
    inst = tiny()
    validate(inst, [[0, 3], [0, 3]])                       # a valid schedule
    with pytest.raises(AssertionError, match="overlaps"):
        # Job 1 op 1 runs on machine 0 from t=2, while job 0 op 0 holds machine 0 until t=3.
        # Precedence is respected (job 1 op 0 ends at 2), so only the overlap rule is broken.
        validate(inst, [[0, 3], [0, 2]])
    with pytest.raises(AssertionError, match="starts before"):
        validate(inst, [[0, 2], [0, 3]])                   # job 0 op 1 starts before op 0 ends
