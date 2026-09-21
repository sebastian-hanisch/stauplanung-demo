"""Kriterien der Preset-Geschichten (stau_stories.py) mit KÜNSTLICHEN Werten: jedes Kriterium kippt einzeln an seiner Schwelle. (Abnahmen über echte Daten prüfen Schwellen nicht;
die stehen in test_preset_stories.py.) Schnell, ohne Löser."""

import pytest

import stau_constants as C
import stau_stories as ST
from stau_evaluation import ListResult

P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT
NAMES = list(C.PRESETS)


# ---------------- 4. jedes Kriterium kippt einzeln an seiner Schwelle (künstliche Werte) ----------------
def fake(restows, valid=True, proven=True, n=10):
    """n gleiche Ladelisten. restows: {Verfahren: Umstauungen}; valid: True/False oder {Verfahren: bool}."""
    v = {k: valid for k in C.STRATEGY_KEYS} if isinstance(valid, bool) else {k: valid.get(k, True) for k in C.STRATEGY_KEYS}
    rs = {k: restows.get(k) for k in C.STRATEGY_KEYS}
    return tuple(ListResult(i, 48, rs, v, proven, "optimal" if proven else "feasible") for i in range(n))


def failing(name, results):
    return [i for i, (ok, _) in enumerate(ST.criteria(name, results)) if not ok]


BASE = {
    "Locker": dict(pod=0, weight=26, repair=0, exact=0),
    "Üblich": dict(pod=0, weight=26, repair=0, exact=0),
    "Knapp": dict(pod=0, weight=26, repair=2, exact=0),
    "Am Limit": dict(pod=0, weight=26, repair=8, exact=3),
    "Viele Häfen": dict(pod=0, weight=32, repair=2, exact=0),
}
POD_VALID = {"Locker": True, "Üblich": False, "Knapp": False, "Am Limit": False, "Viele Häfen": False}


def base(name, **override):
    r = dict(BASE[name], **override)
    return fake(r, valid={P_: POD_VALID[name]})


@pytest.mark.parametrize("name", NAMES)
def test_the_artificial_base_case_satisfies_every_criterion(name):
    assert failing(name, base(name)) == []


@pytest.mark.parametrize("name,override,expected", [
    ("Locker", dict(weight=15), []), ("Locker", dict(weight=14), [2]),
    ("Üblich", dict(weight=15), []), ("Üblich", dict(weight=14), [3]),
    ("Üblich", dict(exact=1), [1]), ("Üblich", dict(repair=1), []),
    ("Knapp", dict(repair=1), []), ("Knapp", dict(repair=0), [1]), ("Knapp", dict(exact=1), [0]),
    ("Am Limit", dict(exact=1, repair=2), []), ("Am Limit", dict(exact=1, repair=1), [1]),
    ("Am Limit", dict(exact=0, repair=8), [0]),
    ("Viele Häfen", dict(weight=25), []), ("Viele Häfen", dict(weight=24), [0]),
    ("Viele Häfen", dict(repair=1), [1]), ("Viele Häfen", dict(repair=2, exact=2), [2]),
])
def test_each_criterion_flips_at_its_threshold(name, override, expected):
    assert failing(name, base(name, **override)) == expected, (name, override)


def test_the_mean_thresholds_use_the_mean_not_every_list():
    r = list(base("Üblich"))
    r[0] = ListResult(0, 48, dict(r[0].restows, repair=10), r[0].valid, True, "optimal")            # Mittel 1.0 = Schwelle
    assert failing("Üblich", tuple(r)) == []
    r[1] = ListResult(1, 48, dict(r[1].restows, repair=1), r[1].valid, True, "optimal")             # Mittel 1.1
    assert failing("Üblich", tuple(r)) == [2]


def test_locker_needs_a_valid_pod_plan_in_every_list_and_zero_restows():
    r = list(base("Locker"))
    r[3] = ListResult(3, 48, r[3].restows, dict(r[3].valid, **{P_: False}), True, "optimal")
    assert failing("Locker", tuple(r)) == [0]
    r = list(base("Locker"))
    r[3] = ListResult(3, 48, dict(r[3].restows, pod=1), r[3].valid, True, "optimal")
    assert failing("Locker", tuple(r)) == [1]


def test_ueblich_needs_the_pod_plan_invalid_in_every_list():
    r = list(base("Üblich"))
    r[0] = ListResult(0, 48, r[0].restows, dict(r[0].valid, **{P_: True}), True, "optimal")
    assert failing("Üblich", tuple(r)) == [0]


def test_viele_haefen_share_of_lists_where_exact_beats_repair_flips_at_70_percent():
    def with_better(k):
        rows = [ListResult(i, 48, dict(BASE["Viele Häfen"], exact=(0 if i < k else 2)), fake({}, valid={P_: False})[0].valid, True, "optimal") for i in range(10)]
        return tuple(rows)
    assert failing("Viele Häfen", with_better(7)) == [] and failing("Viele Häfen", with_better(6)) == [2]


def test_viele_haefen_ignores_lists_where_a_method_has_no_valid_plan():
    rows = list(base("Viele Häfen"))
    for i in range(3):
        rows[i] = ListResult(i, 48, rows[i].restows, dict(rows[i].valid, **{X_: False}), True, "optimal")
    assert failing("Viele Häfen", tuple(rows)) == []                                     # 7 von 10 mit gültigem Plan und besser = 70 %
    rows[3] = ListResult(3, 48, rows[3].restows, dict(rows[3].valid, **{R_: False}), True, "optimal")
    assert failing("Viele Häfen", tuple(rows)) == [2]


@pytest.mark.parametrize("name,override,expected", [
    ("Locker", {}, True), ("Locker", dict(weight=14), False), ("Locker", dict(pod=1), False), ("Locker", dict(weight=15), True),
    ("Üblich", {}, True), ("Üblich", dict(repair=3), False), ("Üblich", dict(repair=2), True), ("Üblich", dict(exact=1), False), ("Üblich", dict(weight=14), False),
    ("Knapp", {}, True), ("Knapp", dict(repair=0), False), ("Knapp", dict(repair=1), True), ("Knapp", dict(exact=1), False),
    ("Am Limit", {}, True), ("Am Limit", dict(exact=0), False), ("Am Limit", dict(exact=1, repair=2), True), ("Am Limit", dict(exact=1, repair=1), False),
    ("Viele Häfen", {}, True), ("Viele Häfen", dict(weight=24), False), ("Viele Häfen", dict(repair=1), True), ("Viele Häfen", dict(repair=0), False),
    ("Viele Häfen", dict(exact=2), False),
])
def test_single_list_story_flips_at_its_threshold(name, override, expected):
    assert ST.holds(name, base(name, **override)[0]) is expected, (name, override)


@pytest.mark.parametrize("name,who", [("Locker", P_), ("Üblich", R_), ("Knapp", X_), ("Am Limit", X_), ("Viele Häfen", R_), ("Locker", W_)])
def test_a_missing_plan_is_never_a_holding_story(name, who):
    valid = {P_: POD_VALID[name], who: False}
    r = fake(dict(BASE[name]), valid=valid)[0]
    assert not ST.holds(name, r)


def test_pod_plan_validity_matters_for_the_single_list_story():
    assert not ST.holds("Üblich", fake(BASE["Üblich"], valid=True)[0])                    # Zielhafen zuerst zulässig: dann gibt es keine Geschichte
    assert not ST.holds("Locker", fake(BASE["Locker"], valid={P_: False})[0])


def test_unknown_preset_name_raises():
    with pytest.raises(KeyError):
        ST.criteria("Unbekannt", base("Locker"))
    with pytest.raises(KeyError):
        ST.holds("Unbekannt", base("Locker")[0])


def test_key_values_lists_the_typical_indicators_of_the_preset():
    kv = ST.key_values("Am Limit", base("Am Limit"))
    assert kv == {X_: 3.0, R_: 8.0} and ST.key_values("Locker", base("Locker")) == {W_: 26.0}


def _mixed(name, k, key, low, high, other=None):
    """10 Listen, k davon mit `key`=high, die übrigen mit low."""
    rows = []
    for i in range(10):
        rs = dict(BASE[name], **(other or {}), **{key: high if i < k else low})
        rows.append(ListResult(i, 48, rs, base(name)[0].valid, True, "optimal"))
    return tuple(rows)


@pytest.mark.parametrize("name", ["Knapp", "Üblich"])
def test_exact_zero_tolerates_a_few_lists_the_solver_did_not_finish_in_time(name):
    """Auf einem langsamen Rechner (CI) findet der Löser die 0 nicht in jeder Liste innerhalb des Limits (CI: 18-19 von 20): bis 15 % Ausreißer sind erlaubt, nicht mehr."""
    idx = 0 if name == "Knapp" else 1
    assert failing(name, _mixed(name, 1, "exact", 0, 1)) == []                              # 90 % der Listen 0
    assert failing(name, _mixed(name, 2, "exact", 0, 1)) == [idx]                           # 80 % genügen nicht


def test_exact_zero_share_counts_a_list_without_valid_plan_as_not_zero():
    rows = list(_mixed("Knapp", 0, "exact", 0, 1))
    rows[0] = ListResult(0, 48, dict(rows[0].restows, exact=None), dict(rows[0].valid, **{X_: False}), True, "infeasible")
    rows[1] = ListResult(1, 48, dict(rows[1].restows, exact=None), dict(rows[1].valid, **{X_: False}), True, "infeasible")
    assert failing("Knapp", tuple(rows)) == [0]                                             # 8 von 10 = 80 %


def test_am_limit_exact_mean_is_inclusive_at_one_half():
    assert failing("Am Limit", _mixed("Am Limit", 5, "exact", 0, 1, dict(repair=9))) == []            # Mittel genau 0,5
    assert failing("Am Limit", _mixed("Am Limit", 4, "exact", 0, 1, dict(repair=9))) == [0]


def test_viele_haefen_repair_mean_is_inclusive_at_one_and_a_half():
    assert failing("Viele Häfen", _mixed("Viele Häfen", 5, "repair", 1, 2)) == []                    # Mittel genau 1,5
    assert failing("Viele Häfen", _mixed("Viele Häfen", 4, "repair", 1, 2)) == [1]


def test_a_method_without_any_valid_plan_fails_its_criterion_instead_of_counting_as_zero():
    none = fake(dict(BASE["Knapp"], exact=None), valid={P_: False, X_: False})
    assert 0 in failing("Knapp", none)
    assert 1 in failing("Üblich", fake(dict(BASE["Üblich"], exact=None), valid={P_: False, X_: False}))


def test_knapp_needs_the_pod_plan_invalid_in_the_single_list():
    assert not ST.holds("Knapp", fake(BASE["Knapp"], valid=True)[0])


def test_viele_haefen_single_list_needs_a_valid_exact_plan():
    assert not ST.holds("Viele Häfen", fake(BASE["Viele Häfen"], valid={P_: False, X_: False})[0])
