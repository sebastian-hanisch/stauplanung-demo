import math
import statistics

import pytest

import stau_constants as C
import stau_evaluation as E
import stau_exact as X
import stau_rules as R
import stau_scenario as SC

P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT


def fake(seed, restows, valid=None, proven=True, n_boxes=40):
    """Ein Listenergebnis mit vorgegebenen Umstauungen je Verfahren."""
    valid = valid or {k: True for k in restows}
    return E.ListResult(seed, n_boxes, dict(restows), dict(valid), proven, "optimal" if proven else "feasible")


# ---------------- Kranspiele ----------------
def test_crane_moves_and_minutes():
    assert E.crane_moves(43, 0) == 43 and E.crane_moves(43, 27) == 43 + 54 == 97
    assert E.crane_minutes(30) == 60 and E.crane_minutes(97) == pytest.approx(97 * 2) and E.crane_minutes(0) == 0
    assert C.CRANE_MOVES_PER_HOUR == 30


# ---------------- Ein Bay, alle Verfahren ----------------
@pytest.fixture(scope="module")
def bay():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 30, 2)
    return inst, lim, E.run_methods(inst, lim, exact_limit=10)


def test_run_methods_returns_the_four_strategies_in_order(bay):
    inst, lim, outs = bay
    assert tuple(o.key for o in outs) == C.STRATEGY_KEYS and all(o.label == C.STRATEGY_LABELS[o.key] for o in outs)
    assert all(o.available for o in outs)


def test_run_methods_matches_the_direct_rules_at_seed_31(bay):
    inst, lim, outs = bay
    pod, wt, rep, ex = outs
    assert pod.restows == 0 and not pod.valid and pod.violations == ("Schwerpunkt",)
    assert wt.restows == 27 and wt.valid and rep.restows == 3 and rep.valid
    assert ex.restows == 0 and ex.valid and ex.exact.status == "optimal" and ex.exact.source == "Löser"
    assert wt.moves == 43 + 54 and rep.moves == 43 + 6 and ex.moves == 43
    assert wt.minutes == pytest.approx(97 * 2) and ex.minutes == pytest.approx(43 * 2)
    assert R.evaluate(inst, ex.stacks, lim) == ex.evaluation


def test_comparison_rows_delta_is_mine_minus_baseline(bay):
    rows = E.comparison_rows(bay[2])
    ref = 27
    assert [r.delta_vs_baseline for r in rows] == [0 - ref, 0, 3 - ref, 0 - ref]
    assert rows[1].delta_vs_baseline == 0 and rows[0].valid is False and rows[3].valid is True
    assert rows[0].kg == 208 and rows[3].kg <= 173 and abs(rows[3].moment) <= 14
    other = E.comparison_rows(bay[2], baseline=R_)
    assert other[2].delta_vs_baseline == 0 and other[1].delta_vs_baseline == 24


def test_exact_interval_of_a_proven_and_an_unproven_result(bay):
    inst, lim, outs = bay
    assert E.exact_interval(E.outcome_of(outs, X_)) == (0, 0, True)
    lim10 = SC.limits(inst, 10, 2)
    o = E.outcome_of(E.run_methods(inst, lim10, exact_limit=1), X_)
    lo, hi, proven = E.exact_interval(o)
    assert lo <= hi <= 5 and proven == (lo == hi)
    assert E.exact_interval(E.Outcome(X_, "x", None, None, None, None)) is None


def test_infeasible_limits_give_the_exact_row_a_reason_and_no_plan():
    inst = SC.custom_instance([(1, 1), (1, 2), (2, 1), (3, 3)], 2, 2, 3)
    outs = E.run_methods(inst, SC.limits(inst, 100, 0), exact_limit=5)                # Neigung 0: Moment -W0+W1 ist nie 0
    ex = E.outcome_of(outs, X_)
    assert not ex.available and ex.stacks is None and ex.evaluation is None and ex.moves is None and ex.minutes is None and ex.restows is None and not ex.valid
    assert ex.exact.status == "infeasible" and "keine zulässige Stauung" in ex.reason
    rows = E.comparison_rows(outs)
    assert rows[3].delta_vs_baseline is None and rows[3].reason == ex.reason and rows[3].available is False
    assert E.exact_interval(ex) is None and ex.violations == ()


def test_unknown_reason_is_distinct(monkeypatch):
    inst = SC.make_instance(6, 5, 90, 5, 2)
    monkeypatch.setattr(X, "solve_exact", lambda *a, **k: X.ExactResult("unknown", None, None, 0, "-", 1.0))
    ex = E.outcome_of(E.run_methods(inst, SC.limits(inst, 0, 1)), X_)
    assert ex.reason == E.NO_PLAN_REASONS["unknown"] and "Zeitlimit" in ex.reason and ex.reason != E.NO_PLAN_REASONS["infeasible"]


def test_run_methods_passes_the_exact_time_limit(monkeypatch):
    seen = []
    real = X.solve_exact
    monkeypatch.setattr(X, "solve_exact", lambda inst, lim, limit=None, **k: seen.append(limit) or real(inst, lim, limit or 1))
    inst = SC.make_instance(6, 5, 90, 5, 4)
    E.run_methods(inst, SC.limits(inst, 60, 2), exact_limit=7)
    E.run_methods(inst, SC.limits(inst, 60, 2))
    assert seen == [7, C.EXACT_LIVE_LIMIT_SECONDS]


# ---------------- Stichprobe ----------------
def test_sample_uses_seeds_from_zero_and_matches_direct_runs():
    res = E.sample(6, 5, 90, 5, 30, 2, n_lists=4, exact_limit=5)
    assert [r.seed for r in res] == [0, 1, 2, 3] and all(r.n_boxes == 27 for r in res)
    for r in res:
        inst = SC.make_instance(6, 5, 90, 5, r.seed)
        outs = E.run_methods(inst, SC.limits(inst, 30, 2), exact_limit=5)
        assert r.restows == {o.key: o.restows for o in outs} and r.valid == {o.key: o.valid for o in outs}
        assert r.exact_status == E.outcome_of(outs, X_).exact.status


def test_sample_is_deterministic_and_independent_of_the_set_seed():
    a = E.sample(6, 5, 90, 5, 60, 2, n_lists=3, exact_limit=5)
    b = E.sample(6, 5, 90, 5, 60, 2, n_lists=3, exact_limit=5)
    assert [(r.seed, r.restows, r.valid) for r in a] == [(r.seed, r.restows, r.valid) for r in b]


def test_sample_progress_reaches_one_in_equal_steps():
    seen = []
    E.sample(4, 3, 90, 3, 100, 5, n_lists=5, exact_limit=2, progress=seen.append)
    assert seen == pytest.approx([0.2, 0.4, 0.6, 0.8, 1.0])


def test_exact_is_never_worse_than_a_valid_rule_in_any_list():
    for r in E.sample(6, 5, 90, 5, 20, 3, n_lists=8, exact_limit=5):
        for k in (W_, R_, P_):
            if r.valid[k] and r.valid[X_]:
                assert r.restows[X_] <= r.restows[k]


# ---------------- Frontier ----------------
def test_frontier_plan_scales_down_for_large_bays():
    assert E.frontier_plan(8, 6) == (C.FRONTIER_POINTS, 8) and E.frontier_plan(6, 10) == (C.FRONTIER_POINTS, 8)              # 60 Zellen: noch normal
    assert E.frontier_plan(12, 8) == (C.FRONTIER_POINTS_LARGE, 6) and E.frontier_plan(7, 9) == (C.FRONTIER_POINTS_LARGE, 6)  # 63 Zellen: klein
    assert len(C.FRONTIER_POINTS_LARGE) < len(C.FRONTIER_POINTS) and C.FRONTIER_LISTS_LARGE < C.FRONTIER_LISTS


@pytest.fixture(scope="module")
def small_frontier():
    return E.frontier(5, 4, 90, 4, 3, points=(0, 30, 100), n_lists=4, exact_limit=3)


def test_frontier_structure_and_same_lists_at_every_point(small_frontier):
    fr = small_frontier
    assert fr.points == (0, 30, 100) and fr.n_lists == 4 and fr.tilt_pct == 3
    for p in fr.points:
        assert [r.seed for r in fr.lists[p]] == [0, 1, 2, 3]
        assert len({r.n_boxes for r in fr.lists[p]}) == 1
    assert [r.n_boxes for r in fr.lists[0]] == [r.n_boxes for r in fr.lists[100]]


def test_frontier_cross_check_against_direct_runs(small_frontier):
    fr = small_frontier
    for p in fr.points:
        for r in fr.lists[p]:
            direct = E.run_list(5, 4, 90, 4, r.seed, p, 3, 3)
            assert direct.restows == r.restows and direct.valid == r.valid


def test_frontier_facts_at_the_loose_end(small_frontier):
    fr = small_frontier
    assert E.curve(fr, P_)[2] == 0 and E.curve_valid_share(fr, P_)[2] == 1.0 and E.curve_valid_share(fr, P_)[0] == 0.0             # Zielhafen zuerst nur bei 100 % zulässig
    assert E.curve(fr, X_)[2] == 0 and E.curve(fr, R_)[2] == 0
    assert E.curve(fr, P_)[0] is None and E.curve(fr, P_)[1] is None                                                            # nie zulässig: kein Mittel


def test_frontier_exact_curve_is_monotone_and_weight_is_flat(small_frontier):
    fr = small_frontier
    ex = [v for v in E.curve(fr, X_) if v is not None]
    assert ex == sorted(ex, reverse=True)                                    # strengere Grenze (kleineres %) = nicht weniger Umstauungen
    w = E.curve(fr, W_)
    assert w[0] == w[1] == w[2] and w[0] is not None                          # Gewicht zuerst hängt nicht von der Grenze ab


def test_frontier_progress_counts_every_solve(monkeypatch):
    seen = []
    E.frontier(4, 3, 90, 3, 5, points=(0, 100), n_lists=3, exact_limit=2, progress=seen.append)
    assert seen == pytest.approx([i / 6 for i in range(1, 7)])


def test_frontier_uses_the_plan_defaults(monkeypatch):
    calls = []
    monkeypatch.setattr(E, "run_list", lambda *a: calls.append(a) or fake(a[4], {P_: 0, W_: 1, R_: 0, X_: 0}))
    fr = E.frontier(12, 8, 90, 5, 2)
    assert fr.points == C.FRONTIER_POINTS_LARGE and fr.n_lists == 6 and len(calls) == 30
    assert sorted({c[5] for c in calls}) == sorted(C.FRONTIER_POINTS_LARGE) and sorted({c[4] for c in calls}) == list(range(6))


def test_curve_proven_share_and_kante():
    lists = {100: (fake(0, {X_: 0, W_: 9}), fake(1, {X_: 0, W_: 9})), 30: (fake(0, {X_: 0, W_: 9}), fake(1, {X_: 1, W_: 9}, proven=False)),
             10: (fake(0, {X_: 2, W_: 9}, proven=False), fake(1, {X_: 2, W_: 9}, proven=False)), 0: (fake(0, {X_: 4, W_: 9}, proven=False), fake(1, {X_: 6, W_: 9}, proven=False))}
    fr = E.Frontier((0, 10, 30, 100), lists, 2, 2)
    assert E.curve_proven(fr) == (0.0, 0.0, 0.5, 1.0)
    assert E.curve(fr, X_) == (5, 2, 0.5, 0)
    assert E.kante(fr, threshold=0.4) == 30 and E.kante(fr) == 10 and E.kante(fr, threshold=1.9) == 10 and E.kante(fr, threshold=2) == 0 and E.kante(fr, threshold=5) is None
    flat = E.Frontier((0, 100), {0: (fake(0, {X_: 0}),), 100: (fake(0, {X_: 0}),)}, 1, 2)
    assert E.kante(flat) is None


# ---------------- Statistik ----------------
def test_values_valid_share_mean_median_ignore_invalid_lists():
    res = [fake(0, {W_: 10, P_: 0}, {W_: True, P_: False}), fake(1, {W_: 20, P_: 0}, {W_: True, P_: False}), fake(2, {W_: 30, P_: 0}, {W_: False, P_: True})]
    assert E.values(res, W_) == [10, 20] and E.values(res, P_) == [0]
    assert E.valid_share(res, W_) == pytest.approx(2 / 3) and E.valid_share(res, P_) == pytest.approx(1 / 3)
    assert E.mean_restows(res, W_) == 15 and E.median_restows(res, W_) == 15 and E.mean_restows(res, P_) == 0
    none = [fake(0, {P_: 0}, {P_: False})]
    assert E.mean_restows(none, P_) is None and E.median_restows(none, P_) is None


def test_unproven_count():
    res = [fake(0, {X_: 0}), fake(1, {X_: 1}, proven=False), fake(2, {X_: 1}, proven=False)]
    assert E.unproven_count(res) == 2


def test_paired_uses_only_lists_where_both_are_valid():
    res = [fake(0, {W_: 10, X_: 2}), fake(1, {W_: 8, X_: 3}, {W_: False, X_: True}), fake(2, {W_: 6, X_: 6})]
    assert E.paired(res, X_, W_) == [-8, 0]
    assert E.paired(res, W_, X_) == [8, 0]


def test_distribution_shares_gains_and_empty():
    res = [fake(i, {W_: 10, X_: x}) for i, x in enumerate([0, 5, 10, 10, 12])]
    d = E.distribution(res, X_, W_)
    assert d.n == 5 and (d.better, d.equal, d.worse) == pytest.approx((0.4, 0.4, 0.2))
    assert d.mean_gain == pytest.approx(-statistics.fmean([-10, -5, 0, 0, 2]))
    assert d.median_gain == 0 and d.better + d.equal + d.worse == pytest.approx(1)
    empty = E.distribution([fake(0, {W_: 1, X_: 1}, {W_: False, X_: True})], X_, W_)
    assert empty.n == 0 and (empty.better, empty.equal, empty.worse, empty.mean_gain, empty.median_gain) == (0, 0, 0, 0, 0)


def test_distribution_is_skewed_when_a_few_lists_carry_the_gain():
    res = [fake(i, {W_: 30, X_: 30}) for i in range(9)] + [fake(9, {W_: 30, X_: 0})]
    d = E.distribution(res, X_, W_)
    assert d.median_gain == 0 and d.mean_gain == pytest.approx(3) and d.equal == pytest.approx(0.9)


def test_verdict_three_states_and_none():
    ref = [10 + (i % 3) for i in range(30)]
    better = [fake(i, {W_: r, X_: r - 5 - (i % 2)}) for i, r in enumerate(ref)]
    worse = [fake(i, {W_: r, X_: r + 5 + (i % 2)}) for i, r in enumerate(ref)]
    noisy = [fake(i, {W_: r, X_: r + (1 if i % 2 else -1)}) for i, r in enumerate(ref)]
    vb, vw, vu = E.verdict(better, X_, W_), E.verdict(worse, X_, W_), E.verdict(noisy, X_, W_)
    assert vb.kind == "better" and vb.diff < 0 and vb.pct < 0 and vb.n == 30 and vb.worse_share == 0
    assert vw.kind == "worse" and vw.diff > 0 and vw.pct > 0 and vw.worse_share == 1
    assert vu.kind == "unclear" and abs(vu.diff) <= C.VERDICT_Z * vu.se and vu.worse_share == pytest.approx(0.5)
    n = E.verdict([fake(0, {W_: 1, X_: 1}, {W_: False, X_: True})], X_, W_)
    assert n.kind == "none" and n.n == 0 and n.pct is None


def test_verdict_diff_se_pct_and_boundary():
    res = [fake(i, {W_: 10 * (i + 1), X_: 10 * (i + 1) + d}) for i, d in enumerate([2, 1, 3, 4])]
    v = E.verdict(res, X_, W_)
    assert v.diff == pytest.approx(2.5) and v.se == pytest.approx(statistics.stdev([2, 1, 3, 4]) / 2) and v.pct == pytest.approx(100 * 2.5 / 25)
    edge = E.verdict([fake(0, {W_: 0, X_: 3}), fake(1, {W_: 0, X_: 1})], X_, W_)                 # Differenz 2, Standardfehler 1: genau 2 SE
    assert edge.diff == pytest.approx(2.0) and edge.se == pytest.approx(1.0) and edge.kind == "unclear"
    assert E.verdict([fake(0, {W_: 0, X_: 3.2}), fake(1, {W_: 0, X_: 1.2})], X_, W_).kind == "worse"
    assert E.verdict([fake(0, {W_: 5, X_: 5}), fake(1, {W_: 5, X_: 5})], X_, W_).kind == "unclear"
    assert E.verdict([fake(0, {W_: 5, X_: 0}), fake(1, {W_: 5, X_: 0})], X_, W_).kind == "better"              # Streuung 0, Unterschied klar
    zero_ref = E.verdict([fake(0, {W_: 0, X_: 4}), fake(1, {W_: 0, X_: 4})], X_, W_)
    assert zero_ref.kind == "worse" and zero_ref.pct is None


def test_real_sample_verdict_exact_beats_weight_first():
    res = E.sample(6, 5, 90, 5, 30, 2, n_lists=8, exact_limit=3)
    v = E.verdict(res, X_, W_)
    assert v.kind == "better" and v.diff < -5 and v.pct < -50 and v.n >= 6
    d = E.distribution(res, X_, W_)
    assert d.better > 0.8 and d.worse == 0 and math.isclose(d.better + d.equal + d.worse, 1)


# ---------------- Nachgeschärft nach der Fehler-Einbau-Prüfung ----------------
def test_exact_interval_order_is_lower_value_proven():
    o = E.Outcome(X_, "x", [[]], None, None, X.ExactResult("feasible", [[]], 5, 2, "Löser", 1.0))
    assert E.exact_interval(o) == (2, 5, False)


def test_list_result_carries_the_exact_proof_status_and_the_time_limit(monkeypatch):
    seen = []
    real = X.solve_exact

    def fake_solver(inst, lim, limit=None, **k):
        seen.append(limit)
        r = real(inst, lim, 2)
        return X.ExactResult("feasible", r.stacks, r.value, 0, r.source, r.wall_ms) if r.stacks is not None else r

    monkeypatch.setattr(X, "solve_exact", fake_solver)
    r = E.run_list(6, 5, 90, 5, 3, 30, 2, 7)
    assert seen == [7] and r.proven is False and r.exact_status == "feasible"
    res = E.sample(4, 3, 90, 3, 100, 5, n_lists=2, exact_limit=9)
    assert seen == [7, 9, 9] and all(not x.proven for x in res)
    fr = E.frontier(4, 3, 90, 3, 5, points=(100,), n_lists=1, exact_limit=11)
    assert seen[-1] == 11 and E.curve_proven(fr) == (0.0,)


def test_verdict_pct_uses_the_reference_mean_of_the_jointly_valid_lists_only():
    res = [fake(0, {W_: 10, X_: 5}), fake(1, {W_: 100, X_: 0}, {W_: True, X_: False})]
    v = E.verdict(res, X_, W_)
    assert v.n == 1 and v.diff == -5 and v.pct == pytest.approx(-50.0)


def test_verdict_worse_share_counts_only_strictly_worse_lists():
    res = [fake(0, {W_: 5, X_: 5}), fake(1, {W_: 5, X_: 5}), fake(2, {W_: 5, X_: 6}), fake(3, {W_: 5, X_: 4})]
    assert E.verdict(res, X_, W_).worse_share == pytest.approx(0.25)


def test_curve_is_the_mean_not_the_median():
    fr = E.Frontier((0,), {0: (fake(0, {X_: 0}), fake(1, {X_: 0}), fake(2, {X_: 9}))}, 3, 2)
    assert E.curve(fr, X_) == (3,)


def test_exact_outcome_equals_the_exact_part_of_run_methods_and_takes_its_own_limit(monkeypatch):
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 30, 2)
    a = E.exact_outcome(inst, lim, exact_limit=10)
    b = E.outcome_of(E.run_methods(inst, lim, exact_limit=10), X_)
    assert a.key == X_ and a.label == C.STRATEGY_LABELS[X_] and a.restows == b.restows == 0 and a.moves == b.moves == 43 and a.exact.status == b.exact.status == "optimal"
    seen = []
    real = X.solve_exact
    monkeypatch.setattr(X, "solve_exact", lambda i, l, limit=None, **k: seen.append(limit) or real(i, l, limit or 1))
    E.exact_outcome(inst, lim, exact_limit=13)
    E.exact_outcome(inst, lim)
    assert seen == [13, C.EXACT_LIVE_LIMIT_SECONDS]
    tilt0 = E.exact_outcome(SC.custom_instance([(1, 1), (1, 2)], 2, 1, 1), SC.limits(SC.custom_instance([(1, 1), (1, 2)], 2, 1, 1), 100, 0), 3)
    assert not tilt0.available and "keine zulässige Stauung" in tilt0.reason
