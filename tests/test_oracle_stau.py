"""Unabhängige Orakel (anderer Rechenweg als der Demo-Code), klein und schnell.

* Tiefster Schwerpunkt: geschlossene Formel (Gewichte absteigend, Rang r liegt in Lage r // Stapel) statt `weight_sorted`.
* Exakt-Löser: dynamische Programmierung über die Stapel (Zustand = restliche Containertypen, Schwerpunkt, Moment) statt CP-SAT
  und statt der Vollaufzählung aller Anordnungen in `test_exact.py`.
"""

import random

import stau_exact as X
import stau_rules as R
import stau_scenario as SC


def _restows(stack):
    return sum(len({q for q, _ in stack[:t] if q < p}) for t, (p, _) in enumerate(stack))


def _dp_optimum(inst, kg_limit, tilt_limit):
    n_c, n_t = inst.n_stacks, inst.n_tiers
    types = sorted(set(inst.boxes))
    index = {t: i for i, t in enumerate(types)}

    def sequences(rem):
        out = []

        def rec(prefix, rem):
            out.append(tuple(prefix))
            if len(prefix) < n_t:
                for i, ty in enumerate(types):
                    if rem[i]:
                        rec(prefix + [ty], rem[:i] + (rem[i] - 1,) + rem[i + 1:])
        rec([], rem)
        return out

    states = {(tuple(inst.boxes.count(t) for t in types), 0, 0): 0}
    for c in range(n_c):
        arm, new = 2 * c - (n_c - 1), {}
        for (rem, kg, mom), cost in states.items():
            for seq in sequences(rem):
                k2 = kg + sum(w * t for t, (_, w) in enumerate(seq))
                if k2 > kg_limit:
                    continue
                r2 = list(rem)
                for b in seq:
                    r2[index[b]] -= 1
                key = (tuple(r2), k2, mom + arm * sum(w for _, w in seq))
                new[key] = min(new.get(key, 10 ** 9), cost + _restows(seq))
        states = new
    done = [cost for (rem, _, mom), cost in states.items() if not any(rem) and abs(mom) <= tilt_limit]
    return min(done) if done else None


def test_dp_oracle_hand_case():
    # 2 Stapel x 2 Lagen, Container (Hafen, Gewicht): (1,1) und (2,1) je zweimal; ohne Schwerpunkt-Grenze braucht man 0 Umstauungen
    inst = SC.custom_instance([(1, 1), (1, 1), (2, 1), (2, 1)], 2, 2, 2)
    assert _dp_optimum(inst, 10 ** 6, 10 ** 6) == 0
    # kleinster Schwerpunkt 2 (zwei Container in Lage 1): beide (1,1) oben, beide (2,1) unten -> 0 Umstauungen und KG = 2
    assert _dp_optimum(inst, 2, 10 ** 6) == 0
    # ein Stapel mit allen vier (Höhe 4 fehlt): ein Bay 1 x 2 mit (1,1),(2,1) und Tilt egal: fern unten -> 0
    assert _dp_optimum(SC.custom_instance([(2, 1), (1, 1)], 1, 2, 2), 10 ** 6, 10 ** 6) == 0
    # Grenze 0 erzwingt beide in Lage 0, geht bei 1 Stapel nicht
    assert _dp_optimum(SC.custom_instance([(2, 1), (1, 1)], 1, 2, 2), 0, 10 ** 6) is None


def test_lowest_centre_of_gravity_matches_closed_formula():
    rng = random.Random(21)
    for _ in range(60):
        n_stacks, n_tiers = rng.randint(2, 12), rng.randint(1, 8)
        n_tiers = max(1, min(n_tiers, 96 // n_stacks))
        inst = SC.make_instance(n_stacks, n_tiers, rng.choice([50, 65, 90, 100]), rng.randint(1, 7), rng.randint(0, 9999))
        weights = sorted((w for _, w in inst.boxes), reverse=True)
        assert R.kg_sum(R.weight_sorted(inst)) == sum(w * (r // n_stacks) for r, w in enumerate(weights))


def test_exact_solver_matches_dynamic_programming():
    rng = random.Random(22)
    for _ in range(14):
        n_stacks, n_tiers = rng.choice([(2, 3), (3, 3), (4, 2), (3, 4), (5, 2)])
        ports = rng.randint(2, 4)
        boxes = [(rng.randint(1, ports), rng.randint(1, 4)) for _ in range(rng.randint(3, min(8, n_stacks * n_tiers)))]
        inst = SC.custom_instance(boxes, n_stacks, n_tiers, ports)
        lim = SC.limits(inst, rng.choice([0, 5, 25, 100]), rng.choice([0, 3, 10, 40]))
        expected = _dp_optimum(inst, lim.kg_limit, lim.tilt_limit)
        res = X.solve_exact(inst, lim, time_limit=20, workers=2)
        if expected is None:
            assert res.status == "infeasible"
        else:
            assert res.status == "optimal" and res.value == res.lower == expected
            assert sum(_restows(s) for s in res.stacks) == expected
