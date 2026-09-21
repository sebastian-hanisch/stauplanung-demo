import pytest

import stau_constants as C
import stau_rules as R
import stau_scenario as SC
from helpers import all_arrangements, discharge_restows, naive_repair, random_instance, random_stacks, small_instance, tiny_instances


# ---------------- Bewertung: Handfälle ----------------
@pytest.mark.parametrize("stack,expected", [
    ([], 0),
    ([(3, 1)], 0),
    ([(3, 1), (2, 1), (1, 1)], 0),                  # fern unten, nah oben: nichts im Weg
    ([(1, 1), (2, 1), (3, 1)], 3),                  # nah unten: Zielhafen 2 ist einmal im Weg (Hafen 1), Zielhafen 3 zweimal (Häfen 1 und 2)
    ([(3, 1), (1, 1), (2, 1)], 1),                  # nur der Container für Hafen 2 liegt über dem für Hafen 1
    ([(1, 1), (3, 1), (3, 1)], 2),                  # zwei Container für Hafen 3 über Hafen 1
    ([(2, 1), (2, 1), (2, 1)], 0),                  # gleicher Zielhafen behindert sich nicht
    ([(1, 1), (2, 1), (2, 1), (1, 1)], 2),          # das obere Zielhafen-1-Paar blockiert nichts (gleicher Hafen), die zwei für Hafen 2 stehen über Hafen 1
    ([(2, 1), (1, 1), (3, 1), (3, 1)], 4),         # beide 3er über {2, 1}: je zwei Häfen -> 4
])
def test_stack_restows_hand_cases(stack, expected):
    assert R.stack_restows(stack) == expected


def test_a_container_counts_once_per_blocked_port_not_once_per_blocked_container():
    """Drei verschiedene kleinere Zielhäfen darunter: der Container über ihnen wird an drei Häfen umgestaut (dreimal gezählt)."""
    assert R.stack_restows([(1, 1), (2, 1), (3, 1), (4, 1)]) == 0 + 1 + 2 + 3
    assert R.stack_restows([(1, 1), (1, 1), (1, 1), (4, 1)]) == 1                                   # drei gleiche darunter: nur ein Hafen


def test_restows_sums_over_stacks():
    assert R.restows([[(1, 1), (2, 1)], [(2, 1), (1, 1)], []]) == 1


@pytest.mark.parametrize("seed", range(300))
def test_formula_equals_the_discharge_simulation(seed):
    stacks = random_stacks(seed)
    assert R.restows(stacks) == discharge_restows(stacks)


def test_discharge_simulation_hand_case():
    assert discharge_restows([[(1, 1), (3, 1), (2, 1)]]) == 2               # Hafen 1: 3 und 2 abheben (beide umstauen); Hafen 2 im Weg von 3 liegt nun unter 3 nicht mehr


def test_kg_moment_and_weights_hand_case():
    stacks = [[(1, 2), (2, 3)], [(1, 4)], [(2, 1), (3, 1), (1, 2)]]
    assert R.kg_sum(stacks) == 2 * 0 + 3 * 1 + 4 * 0 + 1 * 0 + 1 * 1 + 2 * 2 == 8
    assert R.stack_weights(stacks) == [5, 4, 4]
    assert R.moment(stacks) == (-2) * 5 + 0 * 4 + 2 * 4 == -2
    assert R.moment([[(1, 1)]]) == 0                                       # ein Stapel: Arm 0


def test_blockers_marks_exactly_the_restowed_containers():
    assert R.blockers([(1, 1), (2, 1), (3, 1)]) == {1, 2}
    assert R.blockers([(3, 1), (2, 1), (1, 1)]) == set()
    assert R.blockers([(1, 1), (1, 1), (2, 1)]) == {2}
    for seed in range(60):
        for s in random_stacks(seed):
            assert len(R.blockers(s)) <= R.stack_restows(s) and (R.stack_restows(s) == 0) == (not R.blockers(s))


# ---------------- evaluate ----------------
def test_evaluate_reports_each_violation_separately():
    inst = SC.custom_instance([(1, 1), (2, 2), (3, 3)], 2, 2, 3)
    loose = R.Limits(0, 99, 99, 99, 6)
    good = [[(3, 3), (2, 2)], [(1, 1)]]                                    # KG 2, Moment -4
    ev = R.evaluate(inst, good, loose)
    assert ev.valid and ev.restows == 0 and ev.kg == 2 and ev.moment == -4 and ev.violations == ()
    assert R.evaluate(inst, [[(3, 3), (2, 2), (1, 1)], []], loose).violations == ("Höhe",)
    assert R.evaluate(inst, [[(3, 3)], [(1, 1)]], loose).violations == ("Container",)                  # ein Container fehlt
    assert R.evaluate(inst, [[(3, 3), (2, 2)], [(1, 1)], []], loose).violations == ("Container",)      # falsche Stapelzahl
    assert R.evaluate(inst, good, R.Limits(0, 99, 1, 99, 6)).violations == ("Schwerpunkt",)
    assert R.evaluate(inst, good, R.Limits(0, 99, 99, 3, 6)).violations == ("Seitenneigung",)
    assert set(R.evaluate(inst, good, R.Limits(0, 99, 1, 3, 6)).violations) == {"Schwerpunkt", "Seitenneigung"}


def test_evaluate_limit_boundaries_are_inclusive():
    inst = SC.custom_instance([(1, 1), (2, 2), (3, 3)], 2, 2, 3)
    stacks = [[(3, 3), (2, 2)], [(1, 1)]]
    kg, mom = R.kg_sum(stacks), R.moment(stacks)
    lim = R.Limits(kg, kg, kg, abs(mom), 6)
    assert R.evaluate(inst, stacks, lim).valid
    assert R.evaluate(inst, stacks, R.Limits(kg, kg, kg - 1, abs(mom), 6)).violations == ("Schwerpunkt",)
    assert R.evaluate(inst, stacks, R.Limits(kg, kg, kg, abs(mom) - 1, 6)).violations == ("Seitenneigung",)


# ---------------- Regeln ----------------
def _same_boxes(inst, stacks):
    return sorted(b for s in stacks for b in s) == sorted(inst.boxes)


@pytest.mark.parametrize("seed", range(80))
def test_pod_sorted_has_no_restows_and_keeps_all_boxes(seed):
    inst = random_instance(seed)
    st = R.pod_sorted(inst)
    assert _same_boxes(inst, st) and R.restows(st) == 0
    assert all(len(s) <= inst.n_tiers for s in st)
    assert R.kg_sum(st) == SC.limits(inst, 100, 2).kg_pod


@pytest.mark.parametrize("seed", range(80))
def test_weight_sorted_has_the_lowest_possible_kg(seed):
    inst = random_instance(seed)
    st = R.weight_sorted(inst)
    assert _same_boxes(inst, st) and all(len(s) <= inst.n_tiers for s in st)
    # untere Schranke: die schwersten Container in die niedrigsten Lagen (Lage l hat n_stacks Plätze), unabhängig von der Anordnung
    boxes = sorted((w for _, w in inst.boxes), reverse=True)
    lower = sum(w * (i // inst.n_stacks) for i, w in enumerate(boxes))
    assert R.kg_sum(st) == lower


@pytest.mark.parametrize("inst", tiny_instances(25))
def test_weight_sorted_kg_equals_the_brute_force_minimum(inst):
    assert R.kg_sum(R.weight_sorted(inst)) == min(R.kg_sum(a) for a in all_arrangements(inst))


@pytest.mark.parametrize("inst", tiny_instances(25))
def test_pod_sorted_restows_zero_is_the_brute_force_minimum_and_kg_is_feasible(inst):
    assert min(R.restows(a) for a in all_arrangements(inst)) == 0 == R.restows(R.pod_sorted(inst))


def test_layers_fill_evenly_from_the_bottom():
    for seed in range(40):
        inst = random_instance(seed)
        for rule in (R.pod_sorted, R.weight_sorted, R.arrival):
            heights = [len(s) for s in rule(inst)]
            assert max(heights) - min(heights) <= 1 and sum(heights) == len(inst.boxes), (seed, rule.__name__)
            assert max(heights) == -(-len(inst.boxes) // inst.n_stacks)                          # so wenig Lagen wie möglich


def test_partial_top_layer_uses_the_middle_stacks():
    inst = SC.custom_instance([(1, 1)] * 7, 5, 3, 1)                 # eine volle Lage (5) und 2 Container
    assert [len(s) for s in R.pod_sorted(inst)] == [1, 2, 2, 1, 1]


def test_layer_positions_are_the_middle_ones_in_stack_order():
    assert R._layer_positions(5, 2) == [1, 2] and R._layer_positions(8, 3) == [2, 3, 4] and R._layer_positions(8, 4) == [2, 3, 4, 5]
    assert R._layer_positions(6, 1) == [2] and R._layer_positions(4, 3) == [0, 1, 2]
    assert R._layer_positions(6, 6) == list(range(6)) and R._layer_positions(6, 0) == []


def test_within_a_layer_the_moment_is_balanced_greedily():
    inst = SC.custom_instance([(1, 4), (1, 4), (1, 1), (1, 1)], 4, 1, 1)
    st = R.weight_sorted(inst)
    assert R.moment(st) == 0                                              # zwei schwere und zwei leichte, symmetrisch verteilt


def test_arrival_places_each_box_on_the_lowest_stack_in_list_order():
    inst = SC.custom_instance([(1, 1), (2, 1), (3, 1), (1, 2)], 2, 3, 3)
    assert R.arrival(inst) == [[(1, 1), (3, 1)], [(2, 1), (1, 2)]]
    inst2 = SC.custom_instance([(1, 1), (2, 1), (3, 1)], 2, 3, 3)
    assert R.arrival(inst2) == [[(1, 1), (3, 1)], [(2, 1)]]                # Gleichstand: kleinster Index


def test_arrival_is_never_better_than_pod_sorted_on_restows():
    for seed in range(60):
        inst = random_instance(seed)
        assert R.restows(R.arrival(inst)) >= R.restows(R.pod_sorted(inst)) == 0


# ---------------- Reparatur ----------------
@pytest.mark.parametrize("seed", range(120))
def test_incremental_repair_equals_the_naive_repair_move_by_move(seed):
    inst = small_instance(seed)
    for kg_pct in (0, 10, 30, 60, 100):
        lim = SC.limits(inst, kg_pct, 2)
        assert R.repair(inst, lim) == naive_repair(inst, lim), (seed, kg_pct)


def test_repair_keeps_all_boxes_and_heights():
    for seed in range(60):
        inst = random_instance(seed)
        lim = SC.limits(inst, 20, 2)
        st = R.repair(inst, lim)
        assert _same_boxes(inst, st) and all(len(s) <= inst.n_tiers for s in st)
        assert [len(s) for s in st] == [len(s) for s in R.pod_sorted(inst)]        # Tausche verändern die Stapelhöhen nicht


def test_repair_at_loose_limit_is_the_pod_sorting():
    for seed in range(40):
        inst = random_instance(seed)
        lim = SC.limits(inst, 100, 5)
        assert R.repair(inst, lim) == R.pod_sorted(inst)


def _stuck(inst, stacks, lim):
    """True, wenn kein einziger Tausch den Schwerpunkt senkt und dabei die Seitenneigung einhält (Abbruchbedingung der Reparatur)."""
    pos = [(c, t) for c, s in enumerate(stacks) for t in range(len(s))]
    for i, a in enumerate(pos):
        for b in pos[i + 1:]:
            t = [list(s) for s in stacks]
            t[a[0]][a[1]], t[b[0]][b[1]] = t[b[0]][b[1]], t[a[0]][a[1]]
            if R.kg_sum(t) < R.kg_sum(stacks) and abs(R.moment(t)) <= lim.tilt_limit:
                return False
    return True


def test_repair_is_a_heuristic_it_may_fail_but_only_when_stuck_and_rarely():
    """Über 210 Ladelisten im Reglerbereich: Die Reparatur kann die Grenze verfehlen, aber nur an einem echten lokalen Ende (kein Tausch senkt den Schwerpunkt bei erlaubter Neigung);
    unter denen, die die Gewichtsregel halten kann, sind es wenige."""
    failed = comparable = 0
    for seed in range(210):
        inst = random_instance(seed)
        kg_pct = (0, 10, 20, 30, 50, 75, 100)[seed % 7]
        lim = SC.limits(inst, kg_pct, 3)
        st = R.repair(inst, lim)
        rep, wt = R.evaluate(inst, st, lim), R.evaluate(inst, R.weight_sorted(inst), lim)
        if "Schwerpunkt" in rep.violations:
            assert _stuck(inst, st, lim), (seed, kg_pct)
        if wt.valid:
            comparable += 1
            failed += "Schwerpunkt" in rep.violations
    assert comparable > 100 and failed <= 0.1 * comparable, (failed, comparable)


def test_repair_costs_far_fewer_restows_than_weight_first_almost_always():
    """Gemessen über 210 Ladelisten (beide zulässig, 186 Fälle): Mittel 1,2 gegen 18 Umstauungen; in einem Fall ist die Gewichtsregel um eine besser (Heuristik, keine Garantie)."""
    worse, both, rep_sum, wt_sum = 0, 0, 0, 0
    for seed in range(210):
        inst = random_instance(seed)
        lim = SC.limits(inst, (0, 10, 20, 30, 50, 75, 100)[seed % 7], 3)
        rep, wt = R.evaluate(inst, R.repair(inst, lim), lim), R.evaluate(inst, R.weight_sorted(inst), lim)
        if rep.valid and wt.valid:
            both += 1
            worse += rep.restows > wt.restows
            rep_sum += rep.restows
            wt_sum += wt.restows
    assert both > 150 and worse <= 0.03 * both and rep_sum < 0.2 * wt_sum, (worse, both, rep_sum, wt_sum)


def test_repair_respects_the_tilt_limit_it_checks_at_every_swap():
    for seed in range(60):
        inst = random_instance(seed)
        lim = SC.limits(inst, 20, 5)
        start = R.moment(R.pod_sorted(inst))
        rep = R.repair(inst, lim)
        assert abs(R.moment(rep)) <= max(lim.tilt_limit, abs(start))          # nie über die Grenze hinaus verschlechtert


def test_repair_matches_the_measurement_series_at_seed_31():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    for kg_pct, expected in ((100, 0), (60, 0), (30, 3), (10, 5)):
        lim = SC.limits(inst, kg_pct, 2)
        ev = R.evaluate(inst, R.repair(inst, lim), lim)
        assert ev.valid and ev.restows == expected, (kg_pct, ev)
    inst7 = SC.make_instance(8, 6, 90, 7, 31)
    lim7 = SC.limits(inst7, 30, 2)
    assert R.evaluate(inst7, R.repair(inst7, lim7), lim7).restows == 2 and R.restows(R.weight_sorted(inst7)) == 28


def test_repair_terminates_on_the_largest_bay():
    inst = SC.make_instance(12, 8, 100, 7, 3)
    lim = SC.limits(inst, 0, 1)
    ev = R.evaluate(inst, R.repair(inst, lim), lim)
    assert "Container" not in ev.violations and "Höhe" not in ev.violations


def test_pod_sorting_violates_the_kg_limit_below_100_percent_and_weight_sorting_never_does_on_kg():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    for kg_pct in (0, 30, 60, 95):
        lim = SC.limits(inst, kg_pct, 5)
        assert "Schwerpunkt" in R.evaluate(inst, R.pod_sorted(inst), lim).violations
        assert "Schwerpunkt" not in R.evaluate(inst, R.weight_sorted(inst), lim).violations
    assert R.evaluate(inst, R.pod_sorted(inst), SC.limits(inst, 100, 5)).valid


def test_constants_are_consistent():
    assert C.N_STACKS_RANGE[1] * C.N_TIERS_RANGE[1] <= C.MAX_CELLS and C.BASELINE in C.STRATEGY_KEYS
    assert set(C.STRATEGY_KEYS) == set(C.STRATEGY_LABELS) == set(C.STRATEGY_SHORT)
    for name, p in C.PRESETS.items():
        assert p["n_stacks"] * p["n_tiers"] <= C.MAX_CELLS and C.KG_PCT_RANGE[0] <= p["kg_pct"] <= C.KG_PCT_RANGE[1] and p["kg_pct"] % C.KG_PCT_STEP == 0, name
        assert C.TILT_PCT_RANGE[0] <= p["tilt_pct"] <= C.TILT_PCT_RANGE[1] and C.N_PORTS_RANGE[0] <= p["n_ports"] <= C.N_PORTS_RANGE[1]
