"""Tests der Regler-Spezifikation: Permalink-Auswertung (begrenzen, einrasten, Müll ignorieren), Presets innerhalb der Reglergrenzen, Konsistenz mit den Konstanten."""

import math

import pytest

import stau_constants as C
import stau_presets as P
import stau_scenario as SC

S = P.SETTING_SPECS


def test_parse_clamps_to_range():
    spec = S["n_stacks_slider"]
    assert P.parse_setting(spec, "99") == C.N_STACKS_RANGE[1] and P.parse_setting(spec, "-5") == C.N_STACKS_RANGE[0] and P.parse_setting(spec, "6") == 6
    kg = S["kg_slider"]
    assert P.parse_setting(kg, "500") == 100 and P.parse_setting(kg, "-20") == 0
    tilt = S["tilt_slider"]
    assert P.parse_setting(tilt, "0") == 1 and P.parse_setting(tilt, "9") == 5


def test_parse_snaps_to_step_from_lower_bound():
    kg, fill = S["kg_slider"], S["fill_slider"]
    assert P.parse_setting(kg, "27") == 25 and P.parse_setting(kg, "28") == 30 and P.parse_setting(kg, "100") == 100 and P.parse_setting(kg, "99") == 100
    assert P.parse_setting(fill, "52") == 50 and P.parse_setting(fill, "53") == 55 and P.parse_setting(fill, "98") == 100 and P.parse_setting(fill, "100") == 100


def test_parse_ignores_garbage():
    for key in ("n_stacks_slider", "seed_input", "kg_slider"):
        assert P.parse_setting(S[key], "abc") is None and P.parse_setting(S[key], None) is None and P.parse_setting(S[key], "") is None
    assert P.parse_setting(S["view_radio"], "junk") is None
    assert P.parse_setting(S["view_radio"], "weight") is None                   # die Referenz steht immer links, ist keine Wahl rechts
    assert P.parse_setting(S["view_radio"], "exact") == "exact" and P.parse_setting(S["view_radio"], "pod") == "pod"


def test_parse_non_finite_float_is_rejected():
    spec = P.SettingSpec("x", float, 1.0, 0.0, 10.0)
    assert P.parse_setting(spec, "nan") is None and P.parse_setting(spec, "inf") is None
    assert P.parse_setting(spec, "4.5") == 4.5 and P.parse_setting(spec, "99") == 10.0


def test_step_grid_starts_at_the_lower_bound_not_at_zero():
    spec = P.SettingSpec("x", int, 1, 1, 21, 5)
    assert [P.parse_setting(spec, str(v)) for v in (1, 3, 4, 7, 9, 14, 19, 21)] == [1, 1, 6, 6, 11, 16, 21, 21]


def test_specs_match_constants_and_defaults_inside_bounds():
    assert S["n_stacks_slider"].default == C.N_STACKS_DEFAULT and S["kg_slider"].default == C.KG_PCT_DEFAULT and S["seed_input"].default == C.SEED_DEFAULT
    for key, spec in S.items():
        assert P.bounds(key) == (spec.lo, spec.hi)
        if spec.lo is not None:
            assert spec.lo <= spec.default <= spec.hi
            if spec.step and spec.step > 1:
                assert (spec.default - spec.lo) % spec.step == 0
    assert len({spec.url_param for spec in S.values()}) == len(S)
    assert S["view_radio"].default in C.RIGHT_VIEW_KEYS and C.BASELINE not in C.RIGHT_VIEW_KEYS


def test_every_preset_is_inside_bounds_on_the_step_and_within_max_cells():
    assert list(C.PRESETS) == ["Locker", "Üblich", "Knapp", "Am Limit", "Viele Häfen"] and all(len(n) <= 16 for n in C.PRESETS)
    for name, p in C.PRESETS.items():
        assert set(p) == set(P.PRESET_STATE_KEYS)
        for field, state_key in P.PRESET_STATE_KEYS.items():
            spec = S[state_key]
            assert spec.lo <= p[field] <= spec.hi, (name, field)
            if spec.step and spec.step > 1:
                assert (p[field] - spec.lo) % spec.step == 0, (name, field)
        assert p["n_stacks"] * p["n_tiers"] <= C.MAX_CELLS


def test_encoders_roundtrip_through_parse():
    for key, spec in S.items():
        assert P.parse_setting(spec, spec.encoder(spec.default)) == spec.default
    assert P.parse_setting(S["fill_slider"], S["fill_slider"].encoder(75.0)) == 75 and S["seed_input"].encoder(4.0) == "4"


def test_scenario_instance_matches_make_instance_and_casts():
    assert P.scenario_instance(8.0, 6.0, 90.0, 5.0, 31.0) == SC.make_instance(8, 6, 90, 5, 31)
    assert math.isfinite(C.KG_PCT_DEFAULT)


def test_max_bay_is_within_the_cell_limit_and_every_slider_combination_is_valid():
    assert C.N_STACKS_RANGE[1] * C.N_TIERS_RANGE[1] <= C.MAX_CELLS                  # kein berechneter Reglerbereich nötig (min == max Absturz)
    for s in range(C.N_STACKS_RANGE[0], C.N_STACKS_RANGE[1] + 1):
        for t in range(C.N_TIERS_RANGE[0], C.N_TIERS_RANGE[1] + 1):
            assert SC.n_boxes(s, t, C.FILL_PCT_RANGE[0]) >= 1 and s * t <= C.MAX_CELLS
