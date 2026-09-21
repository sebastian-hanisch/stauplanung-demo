"""Jedes Preset erzählt eine Geschichte (Abnahmekriterien in stau_stories.py). Hier wird geprüft, dass sie trägt:

1. in der EINEN Ladeliste, die das Preset zeigt (sonst zeigt das Preset das Gegenteil seines Hilfetexts),
2. im MITTEL über 20 andere Ladelisten (sonst ist das Preset ein Einzelfall, ausgesucht nach dem schönsten Seed),
3. dass die gewählte Liste typisch ist: bei jeder Kennzahl zwischen dem 10. und 90. Perzentil der Listen,
(Die Schwellen selbst prüft test_stories.py mit künstlichen Werten.)

Die Abstimmung selbst steht in tools/tune_presets.py."""

import pytest

import stau_constants as C
import stau_evaluation as E
import stau_stories as ST


P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT
NAMES = list(C.PRESETS)
_cache = {}


def _run(name, seed, limit):
    p = C.PRESETS[name]
    return E.run_list(p["n_stacks"], p["n_tiers"], p["fill_pct"], p["n_ports"], seed, p["kg_pct"], p["tilt_pct"], limit)


# Zeitlimits: Die Aussagen über Exakt sind Aussagen über ein bewiesenes Optimum. Auf einem langsamen Rechner (CI, wenige Kerne) beweist der Löser in 2 s weniger als lokal; darum
# rechnen die Tests großzügig (Ende, sobald bewiesen) und nur "Am Limit", wo ohnehin ein Teil unbewiesen bleibt, mit dem App-Limit von 2 s (die Schwellen dort halten mit Abstand).
POP_LIMIT = {"Am Limit": C.SAMPLE_LIMIT_SECONDS}
SHOWN_LIMIT = C.EXACT_LONG_LIMIT_SECONDS


def _population(name):
    if name not in _cache:
        _cache[name] = tuple(_run(name, s, POP_LIMIT.get(name, 10)) for s in range(C.SAMPLE_LISTS))
    return _cache[name]


# ---------------- 1. in der gezeigten Ladeliste (wie app.py: gleiches Zeitlimit) ----------------
@pytest.mark.parametrize("name", NAMES)
def test_the_story_holds_in_the_list_the_preset_shows(name):
    r = _run(name, C.PRESETS[name]["seed"], SHOWN_LIMIT)
    assert ST.holds(name, r), (name, r)


def test_presets_share_one_list_number_and_bay():
    assert len({(p["seed"], p["n_stacks"], p["n_tiers"], p["fill_pct"], p["tilt_pct"]) for p in C.PRESETS.values()}) == 1
    assert [C.PRESETS[n]["kg_pct"] for n in NAMES] == [100, 60, 30, 0, 30] and C.PRESETS["Viele Häfen"]["n_ports"] == 7 and C.PRESETS["Am Limit"]["n_ports"] == 5


# ---------------- 2. im Mittel der Grundgesamtheit ----------------
@pytest.mark.parametrize("name", NAMES)
def test_the_story_holds_on_average_over_many_lists(name):
    failed = [text for ok, text in ST.criteria(name, _population(name)) if not ok]
    assert not failed, failed


def test_the_population_does_not_contain_the_preset_seed():
    assert C.PRESETS["Locker"]["seed"] not in range(C.SAMPLE_LISTS)                     # sonst wäre die Grundgesamtheit nicht unabhängig vom gezeigten Fall


# ---------------- 3. die gezeigte Liste ist typisch ----------------
def _pct(values, q):
    v = sorted(values)
    return v[int(q * (len(v) - 1))]


@pytest.mark.parametrize("name,key", ST.TYPICAL)
def test_the_shown_list_is_typical(name, key):
    pop = [r.restows[key] for r in _population(name) if r.valid[key]]
    shown = _run(name, C.PRESETS[name]["seed"], SHOWN_LIMIT).restows[key]
    assert _pct(pop, 0.1) <= shown <= _pct(pop, 0.9), (name, key, shown, sorted(pop))
