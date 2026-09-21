import collections

import pytest

import stau_constants as C
import stau_rules as R
import stau_scenario as SC


# ---------------- Zahl der Container ----------------
@pytest.mark.parametrize("stacks,tiers,pct,expected", [
    (8, 6, 90, 43), (8, 6, 100, 48), (8, 6, 50, 24), (4, 3, 50, 6), (5, 3, 50, 8), (7, 3, 50, 11), (12, 8, 95, 91), (4, 3, 100, 12),
])
def test_number_of_boxes_rounds_half_up(stacks, tiers, pct, expected):
    assert SC.n_boxes(stacks, tiers, pct) == expected           # 5x3 mit 50 % = 7,5 -> 8; 7x3 mit 50 % = 10,5 -> 11 (nicht auf gerade gerundet)


def test_number_of_boxes_at_least_one_and_never_more_than_cells():
    assert SC.n_boxes(1, 1, 1) == 1
    for s in range(4, 13):
        for t in range(3, 9):
            for pct in range(C.FILL_PCT_RANGE[0], C.FILL_PCT_RANGE[1] + 1, C.FILL_PCT_STEP):
                assert 1 <= SC.n_boxes(s, t, pct) <= s * t


# ---------------- Ladeliste ----------------
def test_make_instance_is_deterministic_and_within_ranges():
    a, b = SC.make_instance(8, 6, 90, 5, 31), SC.make_instance(8, 6, 90, 5, 31)
    assert a == b and len(a.boxes) == 43 and a.cells == 48
    assert all(1 <= p <= 5 and 1 <= w <= C.WEIGHT_CLASSES for p, w in a.boxes)
    assert SC.make_instance(8, 6, 90, 5, 32) != a


def test_make_instance_fixed_values_of_the_measurement_series():
    """Ladeliste Seed 31 (8 x 6, 90 %, 5 Häfen): gleiche Container wie in der Messreihe (Umstauungen der Gewichtsregel 27, Schwerpunkte 159 und 208)."""
    inst = SC.make_instance(8, 6, 90, 5, 31)
    assert len(inst.boxes) == 43 and inst.boxes[:5] == ((1, 4), (1, 4), (2, 1), (2, 1), (5, 2))
    lim = SC.limits(inst, 30, 2)
    assert (lim.kg_min, lim.kg_pod, lim.kg_limit, lim.tilt_limit, lim.total_weight) == (159, 208, 173, 14, 104)
    assert R.restows(R.weight_sorted(inst)) == 27


def test_make_instance_uses_uniform_pods_and_weights():
    boxes = [b for seed in range(20) for b in SC.make_instance(12, 8, 100, 4, seed).boxes]        # 1920 Container
    pods = collections.Counter(p for p, _ in boxes)
    weights = collections.Counter(w for _, w in boxes)
    assert set(pods) == {1, 2, 3, 4} and set(weights) == {1, 2, 3, 4}
    assert all(0.22 < c / len(boxes) < 0.28 for c in pods.values()) and all(0.22 < c / len(boxes) < 0.28 for c in weights.values())


def test_pod_and_weight_are_independent():
    boxes = [b for seed in range(20) for b in SC.make_instance(12, 8, 100, 4, seed).boxes]
    heavy_share = {p: sum(1 for q, w in boxes if q == p and w >= 3) / sum(1 for q, _ in boxes if q == p) for p in range(1, 5)}
    assert all(0.44 < s < 0.56 for s in heavy_share.values())                                        # in jedem Zielhafen etwa die Hälfte schwer


def test_seed_only_determines_the_boxes_not_the_bay():
    """Ein größerer Bay hängt einfach mehr Container aus demselben Strom an: die Liste des kleineren ist ein Anfangsstück."""
    a, b = SC.make_instance(8, 6, 90, 5, 31), SC.make_instance(10, 5, 90, 5, 31)
    assert len(a.boxes) == 43 and len(b.boxes) == 45 and a.boxes == b.boxes[:43]


def test_make_instance_validation():
    for args in ((0, 6, 90, 5, 1), (8, 0, 90, 5, 1), (8, 6, 90, 0, 1)):
        with pytest.raises(ValueError, match="mindestens 1"):
            SC.make_instance(*args)
    for pct in (0, 101, -5):
        with pytest.raises(ValueError, match="Füllgrad"):
            SC.make_instance(8, 6, pct, 5, 1)


def test_custom_instance_validation():
    ok = SC.custom_instance([(1, 1), (2, 3)], 2, 2, 2)
    assert ok.boxes == ((1, 1), (2, 3)) and ok.cells == 4
    with pytest.raises(ValueError, match="mindestens ein Container"):
        SC.custom_instance([], 2, 2, 2)
    with pytest.raises(ValueError, match="mehr Container als Zellen"):
        SC.custom_instance([(1, 1)] * 5, 2, 2, 2)
    with pytest.raises(ValueError, match="Zielhafen"):
        SC.custom_instance([(3, 1)], 2, 2, 2)
    with pytest.raises(ValueError, match="Zielhafen"):
        SC.custom_instance([(0, 1)], 2, 2, 2)
    with pytest.raises(ValueError, match="Gewichtsklasse"):
        SC.custom_instance([(1, 5)], 2, 2, 2)
    with pytest.raises(ValueError, match="Gewichtsklasse"):
        SC.custom_instance([(1, 0)], 2, 2, 2)
    assert SC.custom_instance([(1.0, 2.0)], 1, 1, 1).boxes == ((1, 2),)


# ---------------- Grenzen ----------------
def test_limits_endpoints_and_monotone():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lo, hi = SC.limits(inst, 0, 2), SC.limits(inst, 100, 2)
    assert lo.kg_limit == lo.kg_min == 159 and hi.kg_limit == hi.kg_pod == 208
    limits = [SC.limits(inst, p, 2).kg_limit for p in range(0, 101, 5)]
    assert limits == sorted(limits) and len(set(limits)) > 5


def test_limits_kg_is_integer_floor_of_the_share():
    inst = SC.make_instance(8, 6, 90, 5, 31)                      # Spielraum 49
    for pct in range(0, 101, 5):
        assert SC.limits(inst, pct, 2).kg_limit == 159 + pct * 49 // 100
    assert SC.limits(inst, 30, 2).kg_limit == 173 and SC.limits(inst, 10, 2).kg_limit == 163 and SC.limits(inst, 60, 2).kg_limit == 188


def test_limits_tilt_is_share_of_the_largest_moment():
    inst = SC.make_instance(8, 6, 90, 5, 31)                      # Gesamtgewicht 104, 8 Stapel
    assert SC.limits(inst, 30, 2).tilt_limit == 2 * 104 * 7 // 100 == 14
    assert SC.limits(inst, 30, 5).tilt_limit == 36 and SC.limits(inst, 30, 0).tilt_limit == 0
    assert SC.limits(inst, 30, 1).total_weight == 104


def test_limits_scale_with_stack_count_and_total_weight():
    a, b = SC.custom_instance([(1, 2)] * 6, 3, 3, 1), SC.custom_instance([(1, 2)] * 6, 4, 3, 1)
    assert SC.limits(a, 0, 50).tilt_limit == 50 * 12 * 2 // 100 and SC.limits(b, 0, 50).tilt_limit == 50 * 12 * 3 // 100


def test_limits_validation():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    for bad in (-1, 101):
        with pytest.raises(ValueError, match="Schwerpunkt-Grenze"):
            SC.limits(inst, bad, 2)
    with pytest.raises(ValueError, match="Seitenneigung"):
        SC.limits(inst, 30, -1)


def test_limits_without_spread_have_equal_bounds():
    """Alle Container gleich schwer und ein Stapel: kein Spielraum, jede Grenze ist der einzige Schwerpunkt."""
    inst = SC.custom_instance([(1, 2)] * 4, 1, 4, 1)
    lim = SC.limits(inst, 50, 2)
    assert lim.kg_min == lim.kg_pod == lim.kg_limit == 2 * (0 + 1 + 2 + 3)
