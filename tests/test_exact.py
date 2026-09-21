import random

import pytest

import stau_exact as X
import stau_rules as R
import stau_scenario as SC
from helpers import all_arrangements, random_instance, tiny_instances


def brute_min(inst, lim):
    """Kleinste Zahl von Umstauungen über ALLE Anordnungen, die beide Grenzen einhalten (None, wenn keine zulässig ist)."""
    best = None
    for a in all_arrangements(inst):
        if R.kg_sum(a) > lim.kg_limit or abs(R.moment(a)) > lim.tilt_limit:
            continue
        r = R.restows(a)
        if best is None or r < best:
            best = r
    return best


TINY = tiny_instances(300)


# ---------------- Modell gegen Brute Force ----------------
@pytest.mark.parametrize("seed", range(200))
def test_solver_equals_brute_force_on_tiny_lists(seed):
    inst = TINY[seed]
    rng = random.Random(1000 + seed)
    lim = SC.limits(inst, rng.choice([0, 10, 25, 50, 75, 100]), rng.choice([0, 5, 15, 30, 60]))
    bf = brute_min(inst, lim)
    res = X.solve_exact(inst, lim, time_limit=20, use_hint=(seed % 2 == 0), workers=2)
    if bf is None:
        assert res.status == "infeasible" and res.stacks is None and res.value is None and res.proven
        return
    assert res.status == "optimal" and res.proven and res.value == bf and res.lower == bf
    ev = R.evaluate(inst, res.stacks, lim)
    assert ev.valid and ev.restows == res.value                              # der Plan des Lösers besteht die unabhängige Prüfung und die Zielfunktion stimmt


@pytest.mark.parametrize("seed", range(200, 300))
def test_solver_equals_brute_force_on_strict_tiny_lists(seed):
    """Strenge Grenzen (Schwerpunkt bis 10 % des Spielraums): hier ist das Optimum oft größer als 0, also prüft der Vergleich die Zielfunktion und nicht nur die Zulässigkeit."""
    inst = TINY[seed]
    rng = random.Random(5000 + seed)
    lim = SC.limits(inst, rng.choice([0, 0, 5, 10]), rng.choice([10, 20, 30]))
    bf = brute_min(inst, lim)
    res = X.solve_exact(inst, lim, time_limit=20, use_hint=(seed % 2 == 0), workers=2)
    if bf is None:
        assert res.status == "infeasible"
    else:
        assert res.status == "optimal" and res.value == bf and R.evaluate(inst, res.stacks, lim).valid


def test_the_strict_tiny_lists_contain_positive_optima():
    """Gegenprobe der Gegenprobe: unter den strengen Fällen gibt es Optima über 0 (sonst wäre der Vergleich zu leicht)."""
    positives = 0
    for seed in range(200, 300):
        rng = random.Random(5000 + seed)
        lim = SC.limits(TINY[seed], rng.choice([0, 0, 5, 10]), rng.choice([10, 20, 30]))
        bf = brute_min(TINY[seed], lim)
        positives += bf is not None and bf > 0
    assert positives >= 15


def test_infeasible_tilt_is_detected_and_proven():
    inst = SC.custom_instance([(1, 1), (1, 2)], 2, 1, 1)                     # Moment = -W0 + W1 ist nie 0 (Gewichte 1 und 2)
    res = X.solve_exact(inst, SC.limits(inst, 100, 0), time_limit=5)
    assert res.status == "infeasible" and res.stacks is None and res.value is None and res.proven


def test_infeasible_kg_limit_below_the_minimum_is_detected():
    inst = SC.custom_instance([(1, 3), (1, 2), (1, 1)], 1, 3, 1)             # ein Stapel: der Schwerpunkt ist 0*.. + 1*.. festgelegt (kleinster: schwerster unten)
    lim = SC.limits(inst, 100, 100)
    tight = R.Limits(lim.kg_min, lim.kg_pod, lim.kg_min - 1, lim.tilt_limit, lim.total_weight)
    assert X.solve_exact(inst, tight, time_limit=5).status == "infeasible"
    assert X.solve_exact(inst, R.Limits(lim.kg_min, lim.kg_pod, lim.kg_min, lim.tilt_limit, lim.total_weight), time_limit=5).status == "optimal"


def test_limits_are_inclusive_at_the_exact_boundary():
    """Die Grenzen sind einschließlich: mit L = tiefster Schwerpunkt und B = Moment dieses Plans gibt es einen Plan, mit L - 1 keinen."""
    inst = SC.custom_instance([(1, 2), (2, 1), (3, 3), (2, 2)], 2, 2, 3)
    kmin = SC.limits(inst, 0, 100).kg_min
    lim = R.Limits(kmin, kmin + 5, kmin, 100, 8)
    assert X.solve_exact(inst, lim, time_limit=5).status == "optimal"
    assert X.solve_exact(inst, R.Limits(kmin, kmin + 5, kmin - 1, 100, 8), time_limit=5).status == "infeasible"


# ---------------- Optimum gegen die Regeln ----------------
@pytest.mark.parametrize("seed", range(24))
def test_optimum_is_at_most_every_valid_rule(seed):
    inst = random_instance(seed, max_stacks=8, max_tiers=6)
    lim = SC.limits(inst, (5, 15, 30, 50, 75, 100)[seed % 6], 3)
    res = X.solve_exact(inst, lim, time_limit=3, workers=4)
    assert res.status in ("optimal", "feasible", "unknown") and res.lower <= (res.value if res.value is not None else 0)
    for rule in (R.pod_sorted, R.weight_sorted, R.repair):
        st = rule(inst, lim) if rule is R.repair else rule(inst)
        ev = R.evaluate(inst, st, lim)
        if ev.valid and res.value is not None:
            assert res.value <= ev.restows, (seed, rule.__name__)
    if res.stacks is not None:
        assert R.evaluate(inst, res.stacks, lim).valid


def test_stricter_kg_limit_never_needs_fewer_restows():
    for seed in range(12):
        inst = random_instance(seed, max_stacks=7, max_tiers=5)
        values = []
        for pct in (100, 60, 30, 10):
            r = X.solve_exact(inst, SC.limits(inst, pct, 3), time_limit=5, workers=4)
            if r.status == "optimal":
                values.append(r.value)
        assert values == sorted(values), (seed, values)


def test_with_and_without_the_start_solution_the_proven_optimum_is_the_same():
    for seed in range(10):
        inst = random_instance(seed, max_stacks=7, max_tiers=5)
        lim = SC.limits(inst, 30, 3)
        a, b = X.solve_exact(inst, lim, time_limit=10, use_hint=True), X.solve_exact(inst, lim, time_limit=10, use_hint=False)
        if a.status == "optimal" and b.status == "optimal":
            assert a.value == b.value


# ---------------- Optimum 0 und Regel ----------------
def test_zero_restows_is_proven_without_the_solver(monkeypatch):
    inst = SC.make_instance(8, 6, 90, 5, 31)
    monkeypatch.setattr(X, "_solve_model", lambda *a, **k: pytest.fail("Löser darf nicht laufen"))
    res = X.solve_exact(inst, SC.limits(inst, 100, 2))
    assert (res.status, res.value, res.lower, res.source) == ("optimal", 0, 0, "Regel") and res.proven
    assert R.evaluate(inst, res.stacks, SC.limits(inst, 100, 2)).valid


def test_preset_values_at_seed_31():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    for pct in (60, 30):
        lim = SC.limits(inst, pct, 2)
        res = X.solve_exact(inst, lim, time_limit=10)
        assert res.status == "optimal" and res.value == 0 and res.proven and R.evaluate(inst, res.stacks, lim).valid, pct
    lim = SC.limits(inst, 10, 2)
    rep = R.evaluate(inst, R.repair(inst, lim), lim).restows
    res = X.solve_exact(inst, lim, time_limit=2)
    assert res.value <= rep == 5 and res.lower <= res.value and R.evaluate(inst, res.stacks, lim).valid
    inst7 = SC.make_instance(8, 6, 90, 7, 31)
    lim7 = SC.limits(inst7, 30, 2)
    assert X.solve_exact(inst7, lim7, time_limit=10).value == 0


# ---------------- Zeitlimit-Pfade ----------------
class _FakeSolver:
    """Ersatz für CpSolver: meldet UNKNOWN (Zeitlimit ohne Plan)."""
    status = None

    def __init__(self):
        self.parameters = type("P", (), {})()

    def Solve(self, model):
        from ortools.sat.python import cp_model
        return self.status if self.status is not None else cp_model.UNKNOWN

    def BestObjectiveBound(self):
        return 2.4


def test_time_limit_without_plan_falls_back_to_the_rule_and_is_not_proven(monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setattr(cp_model, "CpSolver", _FakeSolver)
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 10, 2)
    res = X.solve_exact(inst, lim, time_limit=1)
    rep = R.evaluate(inst, R.repair(inst, lim), lim)
    assert rep.valid
    assert res.status == "feasible" and not res.proven and res.source == "Regel" and res.value == rep.restows
    assert res.lower == 3 and res.lower <= res.value                          # ceil(2,4): die Schranke des Lösers, ganzzahlig aufgerundet


def test_time_limit_without_plan_and_without_valid_rule_is_unknown(monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setattr(cp_model, "CpSolver", _FakeSolver)
    inst = SC.custom_instance([(1, 1), (1, 2)], 2, 1, 1)
    res = X.solve_exact(inst, SC.limits(inst, 100, 0), time_limit=1)           # keine zulässige Stauung, der Löser sagt nur UNKNOWN
    assert res.status == "unknown" and res.stacks is None and res.value is None and not res.proven and res.source == "-" and res.lower == 3


def test_solver_infeasible_status_is_reported_as_proven(monkeypatch):
    from ortools.sat.python import cp_model

    class Infeasible(_FakeSolver):
        status = cp_model.INFEASIBLE

    monkeypatch.setattr(cp_model, "CpSolver", Infeasible)
    inst = SC.make_instance(6, 5, 90, 5, 2)
    res = X.solve_exact(inst, SC.limits(inst, 0, 1), time_limit=1)
    assert res.status == "infeasible" and res.proven and res.stacks is None and res.source == "-"


def test_real_time_limit_never_reports_an_unproven_value_as_optimum():
    inst = SC.make_instance(12, 8, 100, 7, 3)
    lim = SC.limits(inst, 0, 1)
    res = X.solve_exact(inst, lim, time_limit=0.2, workers=4)
    if res.status == "optimal":
        assert res.value == res.lower
    else:
        assert res.status in ("feasible", "unknown") and not res.proven and res.lower <= (res.value or 0)
    assert res.wall_ms < 5000


def test_solver_plan_replaces_the_rule_only_when_not_worse():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 30, 2)
    res = X.solve_exact(inst, lim, time_limit=10)
    rep = R.evaluate(inst, R.repair(inst, lim), lim)
    assert rep.restows == 3 and res.value == 0 and res.source == "Löser"


def test_result_wall_time_is_reported():
    inst = SC.make_instance(6, 5, 90, 5, 4)
    res = X.solve_exact(inst, SC.limits(inst, 30, 2), time_limit=5)
    assert res.wall_ms > 0 and isinstance(res.wall_ms, float)


def test_one_container_and_full_bay_edge_cases():
    one = SC.custom_instance([(2, 3)], 4, 3, 2)
    r = X.solve_exact(one, SC.limits(one, 100, 100), time_limit=5)
    assert r.status == "optimal" and r.value == 0
    full = SC.make_instance(4, 3, 100, 3, 9)                                 # jede Zelle belegt: Höhen und Anzahl fest
    rf = X.solve_exact(full, SC.limits(full, 100, 5), time_limit=10)
    assert rf.status == "optimal" and all(len(s) == 3 for s in rf.stacks)


# ---------------- Nachgeschärft nach der Fehler-Einbau-Prüfung ----------------
from ortools.sat.python import cp_model as _cp

_REAL_SOLVER = _cp.CpSolver                                                   # vor dem Austausch per monkeypatch gemerkt


class _FeasibleWrapper:
    """Echter CP-SAT, meldet aber immer FEASIBLE (Zeitlimit ohne Beweis) und eine untere Schranke von Zielwert - 1,5 (fraktional: Aufrunden ist prüfbar)."""

    def __init__(self):
        self._s = _REAL_SOLVER()
        self.parameters = self._s.parameters

    def Solve(self, model):
        from ortools.sat.python import cp_model
        st = self._s.Solve(model)
        return cp_model.FEASIBLE if st == cp_model.OPTIMAL else st

    def BestObjectiveBound(self):
        return self._s.ObjectiveValue() - 1.5

    def __getattr__(self, name):
        return getattr(self._s, name)


def test_a_feasible_solver_result_keeps_its_plan_is_not_proven_and_rounds_the_bound_up(monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setattr(cp_model, "CpSolver", _FeasibleWrapper)
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 10, 2)                                              # Optimum liegt über 0 (Reparatur 5, Löser findet 2 bis 3)
    res = X.solve_exact(inst, lim, time_limit=3, workers=4)
    assert res.status == "feasible" and not res.proven and res.source == "Löser" and res.stacks is not None
    assert R.evaluate(inst, res.stacks, lim).valid and R.evaluate(inst, res.stacks, lim).restows == res.value and 2 <= res.value <= 5
    assert res.lower == res.value - 1                                         # ceil(Wert - 1,5): weder abgerundet noch gleich dem Wert


def test_a_worse_solver_plan_never_replaces_the_rule_but_an_equal_one_does(monkeypatch):
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 10, 2)
    rule = R.evaluate(inst, R.repair(inst, lim), lim).restows                 # 5
    worse = R.weight_sorted(inst)
    monkeypatch.setattr(X, "_solve_model", lambda *a, **k: ("feasible", worse, R.restows(worse), 0))
    res = X.solve_exact(inst, lim)
    assert res.source == "Regel" and res.value == rule and res.stacks == R.repair(inst, lim) and res.status == "feasible"
    other = R.pod_sorted(inst)                                                # anderer Plan, gleich viele Umstauungen wie die Regel angegeben
    monkeypatch.setattr(X, "_solve_model", lambda *a, **k: ("optimal", other, rule, rule))
    res2 = X.solve_exact(inst, lim)
    assert res2.source == "Löser" and res2.status == "optimal" and res2.stacks == other
