"""AppTest: Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, Kennzahlen im 2 x 2-Raster, Stichprobe und Kurve auf Knopfdruck, Urteil in allen Zuständen,
Exakt-Tab, Vergleichstabelle, Texte."""

import pathlib

import pytest
from streamlit.proto.Metric_pb2 import Metric as MetricProto
from streamlit.testing.v1 import AppTest

import stau_constants as C
import stau_evaluation as E
import stau_exact as X
from stau_evaluation import Verdict
from stau_presets import SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = ("Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
          "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
          "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)")
P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=240)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        (at.number_input if key.endswith("_input") else at.slider)(key=key).set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value, m.delta) for m in at.metric[:4]]


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception
    return at


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer():
    at = fresh()
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]                # genau EIN Header
    assert len(at.title) == 1 and "Schiffsstauplanung" in at.title[0].value
    assert any(v.value.startswith("## 🎯") for v in at.markdown)
    assert [s.value for s in at.subheader] == ["📐 Was kostet die Stabilität?"]
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – vollständiger Methodenvergleich", "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5 and all(len(n) <= 16 for n in presets)


def test_main_metrics_are_2x2_with_the_four_strategies_and_signed_deltas():
    at = fresh()
    assert [m[0] for m in main_metrics(at)] == [C.STRATEGY_LABELS[k] for k in C.STRATEGY_KEYS]
    assert [m[1] for m in main_metrics(at)] == ["0 ⚠️", "27", "3", "0"]
    assert [m[2] for m in main_metrics(at)] == ["-27", "", "-24", "-27"]
    colors = [m.proto.color for m in at.metric[:4]]
    assert colors == [MetricProto.GRAY, MetricProto.GRAY, MetricProto.GREEN, MetricProto.GREEN]     # ein unzulässiger Plan gilt nicht als "besser"
    assert all(len(m[0]) <= 24 for m in main_metrics(at))


def test_crane_move_message_and_bay_charts():
    at = fresh()
    msg = [i.value for i in at.info if "Kranspiele" in i.value][0]
    assert "43 Container + 2 × Umstauungen" in msg and "**97 Spiele** (194 min" in msg and "**43** (86 min)" in msg and "**108 min** weniger" in msg
    assert "Zielhafen zuerst verletzt die Schwerpunkt-Grenze" in msg
    assert len(at.get("plotly_chart")) >= 7                                             # 2 im Bay-Blick + 4 im Methodenvergleich + Vergleich
    assert any("roter Rand = muss umgestaut werden" in c.value and "1 blau" in c.value and "5 rosa" in c.value for c in at.caption)


def test_sidebar_shows_the_number_of_boxes():
    at = fresh()
    assert any("= 43 Container in 48 Zellen" in c.value for c in at.sidebar.caption)
    set_and_run(at, n_stacks_slider=10, n_tiers_slider=7, fill_slider=50)
    assert any("= 35 Container in 70 Zellen" in c.value for c in at.sidebar.caption)


# ---------------------------------------------------------------------------------------------------
# Presets, Permalink
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds_and_shows_its_story(name):
    at = fresh()
    click(at, name)
    p = C.PRESETS[name]
    assert at.slider(key="kg_slider").value == p["kg_pct"] and at.slider(key="n_ports_slider").value == p["n_ports"] and at.number_input(key="seed_input").value == p["seed"]
    for state_key, spec in SETTING_SPECS.items():
        if spec.lo is not None:
            value = at.session_state[state_key]
            assert spec.lo <= value <= spec.hi and (spec.step in (None, 1) or (value - spec.lo) % spec.step == 0)
    m = {m[0]: m[1] for m in main_metrics(at)}
    pod, wt, rep, ex = (m[C.STRATEGY_LABELS[k]] for k in C.STRATEGY_KEYS)
    if name == "Locker":
        assert pod == "0" and ex == "0" and int(wt) >= 15                             # Zielhafen zuerst ist zulässig (kein ⚠️)
    elif name == "Üblich":
        assert pod == "0 ⚠️" and ex == "0" and int(wt) >= 15 and int(rep) <= 2
    elif name == "Knapp":
        assert pod == "0 ⚠️" and ex == "0" and int(rep) >= 1
    elif name == "Am Limit":
        assert pod == "0 ⚠️" and int(rep) >= 2 and ex.lstrip("≤ ").isdigit() and int(ex.lstrip("≤ ")) < int(rep)              # AP 6 schärft die Geschichte, hier nur die Ordnung
    else:
        assert pod == "0 ⚠️" and int(wt) >= 25 and int(rep) >= 1 and ex == "0"


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(kg="27", fp="52", vw="junk", ns="abc", tl="99", nt="1")
    assert at.slider(key="kg_slider").value in (25, 30) and at.slider(key="fill_slider").value == 50
    assert at.radio(key="view_radio").value == C.VIEW_DEFAULT and at.slider(key="n_stacks_slider").value == C.N_STACKS_DEFAULT
    assert at.slider(key="tilt_slider").value == C.TILT_PCT_RANGE[1] and at.slider(key="n_tiers_slider").value == C.N_TIERS_RANGE[0]


def test_permalink_roundtrip_reflects_settings():
    at = fresh(kg="60", ns="6", nt="5", np="4", seed="11", vw="repair")
    assert at.slider(key="kg_slider").value == 60 and at.radio(key="view_radio").value == "repair" and at.number_input(key="seed_input").value == 11
    assert at.slider(key="n_stacks_slider").value == 6 and at.slider(key="n_tiers_slider").value == 5 and at.slider(key="n_ports_slider").value == 4     # jeder Parameter der Adresszeile kommt an
    assert at.query_params["kg"] in ("60", ["60"]) and at.query_params["np"] in ("4", ["4"])


def test_seed_button_uses_the_random_draw_unchanged(monkeypatch):
    import random
    monkeypatch.setattr(random, "randint", lambda lo, hi: hi)
    at = fresh()
    click(at, "🎲 Neue Ladeliste")
    assert at.number_input(key="seed_input").value == C.SEED_RANGE[1]


def test_seed_button_changes_only_the_seed():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    click(at, "🎲 Neue Ladeliste")
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before
    assert C.SEED_RANGE[0] <= at.number_input(key="seed_input").value <= C.SEED_RANGE[1]


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [
    ("n_stacks_slider", 4), ("n_stacks_slider", 12), ("n_tiers_slider", 3), ("n_tiers_slider", 8), ("fill_slider", 50), ("fill_slider", 100), ("n_ports_slider", 2),
    ("n_ports_slider", 7), ("seed_input", 0), ("seed_input", 9999), ("kg_slider", 0), ("kg_slider", 100), ("tilt_slider", 1), ("tilt_slider", 5),
])
def test_every_slider_at_min_and_max(key, value):
    at = set_and_run(fresh(), **{key: value})
    assert len(at.get("plotly_chart")) >= 2 and [m[0] for m in main_metrics(at)] == [C.STRATEGY_LABELS[k] for k in C.STRATEGY_KEYS]


def test_largest_and_smallest_bays():
    big = set_and_run(fresh(), n_stacks_slider=12, n_tiers_slider=8, fill_slider=100, n_ports_slider=7, kg_slider=30)
    assert all(m[1] != "" for m in main_metrics(big))
    small = set_and_run(fresh(), n_stacks_slider=4, n_tiers_slider=3, fill_slider=50, n_ports_slider=2)
    assert [m[0] for m in main_metrics(small)] == [C.STRATEGY_LABELS[k] for k in C.STRATEGY_KEYS]
    exact = main_metrics(small)[3][1]
    assert exact == "–" or exact.lstrip("≤ ").isdigit()                                    # sehr kleines Bay: kann zu wenig Neigungs-Spielraum haben


@pytest.fixture
def clean_cache():
    """Die App cached Szenarien prozessweit: Tests mit ersetztem Löser dürfen weder fremde Ergebnisse sehen noch eigene hinterlassen."""
    import streamlit as st
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def test_exact_without_plan_shows_dash_and_error_and_no_crane_message(monkeypatch, clean_cache):
    monkeypatch.setattr(X, "solve_exact", lambda *a, **k: X.ExactResult("infeasible", None, None, 0, "-", 1.0))
    at = fresh()
    assert main_metrics(at)[3][1] == "–" and any("keine zulässige Stauung" in e.value for e in at.error)
    assert not any("Kranspiele =" in i.value for i in at.info)                            # keine Kranspiele-Meldung ohne Exakt-Plan


def test_exact_unproven_is_shown_as_an_upper_bound(monkeypatch, clean_cache):
    import stau_rules as R

    def unproven(inst, lim, *a, **k):
        plan = R.repair(inst, lim)
        return X.ExactResult("feasible", plan, R.restows(plan), R.restows(plan) - 1, "Regel", 1.0)

    monkeypatch.setattr(X, "solve_exact", unproven)
    at = fresh()
    rep = main_metrics(at)[2][1]
    assert main_metrics(at)[3][1] == f"≤ {rep}"
    assert f"zwischen {int(rep) - 1} und {rep}" in at.metric[3].help


# ---------------------------------------------------------------------------------------------------
# Stichprobe und Kurve auf Knopfdruck
# ---------------------------------------------------------------------------------------------------
SMALL = dict(n_stacks_slider=4, n_tiers_slider=4)


def test_before_the_button_nothing_is_computed_and_after_it_everything_is_shown():
    at = set_and_run(fresh(), **SMALL)
    assert any("Noch nichts berechnet" in i.value for i in at.info)
    assert not [s for s in at.success if "Exakt gegen" in s.value]
    click(at, "📊 Stichprobe und Kurve berechnen")
    assert not any("Noch nichts berechnet" in i.value for i in at.info)
    texts = [x.value for x in list(at.success) + list(at.warning) + list(at.info)]
    assert any("Exakt gegen Gewicht zuerst" in t for t in texts) and any("Exakt gegen Sortieren + Reparatur" in t for t in texts) and any("Sortieren + Reparatur gegen Gewicht zuerst" in t for t in texts)
    assert len(at.get("plotly_chart")) >= 7 + 3                                        # dazu Verteilung, Gewinn, Frontier
    caps = " ".join(c.value for c in at.caption)
    assert "Basis: 20 Ladelisten (Seeds 0-19" in caps and "Basis: 7 Grenzwerte × 8 Ladelisten (Seeds 0-7)" in caps and "nicht bewiesen" in caps


def test_stale_curve_after_a_setting_change_is_flagged_and_not_shown():
    at = set_and_run(fresh(), **SMALL)
    click(at, "📊 Stichprobe und Kurve berechnen")
    set_and_run(at, kg_slider=60)
    assert any("bezogen sich auf andere Einstellungen" in i.value for i in at.info)
    assert not [s for s in list(at.success) + list(at.warning) if "Exakt gegen" in s.value]
    set_and_run(at, kg_slider=30)                                                        # zurück: das gespeicherte Ergebnis passt wieder
    assert [s for s in at.success if "Exakt gegen Gewicht zuerst" in s.value]


def test_the_seed_does_not_invalidate_the_sample_but_tilt_does():
    at = set_and_run(fresh(), **SMALL)
    click(at, "📊 Stichprobe und Kurve berechnen")
    set_and_run(at, seed_input=77)
    assert [s for s in at.success if "Exakt gegen Gewicht zuerst" in s.value]
    set_and_run(at, tilt_slider=4)
    assert any("bezogen sich auf andere Einstellungen" in i.value for i in at.info)


def _fake_verdict(monkeypatch, kind, pct):
    monkeypatch.setattr(E, "verdict", lambda res, key, ref=C.BASELINE: Verdict(kind, -2.0 if kind == "better" else 2.0, 0.5, pct, 20, 0.25))


@pytest.mark.parametrize("kind,pct,expected", [
    ("better", -40.0, "im Mittel **40 % weniger** Umstauungen (2.0 je Ladeliste, Standardfehler 0.50)."),
    ("better", None, "im Mittel **2.0 weniger** Umstauungen (2.0 je Ladeliste, Standardfehler 0.50)."),
    ("worse", 25.0, "im Mittel **25 % mehr** Umstauungen (2.0 je Ladeliste, Standardfehler 0.50)."),
    ("worse", None, "im Mittel **2.0 mehr** Umstauungen (2.0 je Ladeliste, Standardfehler 0.50)."),
])
def test_verdict_sentences_in_the_four_variants(monkeypatch, clean_cache, kind, pct, expected):
    _fake_verdict(monkeypatch, kind, pct)
    at = set_and_run(fresh(), **SMALL)
    click(at, "📊 Stichprobe und Kurve berechnen")
    texts = [x.value for x in (at.success if kind == "better" else at.warning) if "Ladelisten" in x.value and "im Mittel" in x.value]
    assert len(texts) == 3 and all(expected in t for t in texts)
    assert all(t.count("(") == t.count(")") for t in texts)


def test_verdict_unclear_and_none(monkeypatch, clean_cache):
    _fake_verdict(monkeypatch, "unclear", 1.0)
    at = set_and_run(fresh(), **SMALL)
    click(at, "📊 Stichprobe und Kurve berechnen")
    us = [i.value for i in at.info if "Kein klarer Unterschied" in i.value]
    assert len(us) == 3 and all("Rauschens" in u for u in us)
    _fake_verdict(monkeypatch, "none", None)
    at2 = set_and_run(fresh(), **SMALL)
    click(at2, "📊 Stichprobe und Kurve berechnen")
    assert len([i for i in at2.info if "In keiner Ladeliste sind beide Verfahren zulässig" in i.value]) == 3


def test_real_verdicts_exact_beats_weight_first_and_repair():
    at = set_and_run(fresh(), n_stacks_slider=6, n_tiers_slider=5)
    click(at, "📊 Stichprobe und Kurve berechnen")
    assert [s for s in at.success if "Exakt gegen Gewicht zuerst" in s.value and "weniger" in s.value]
    assert [s for s in at.success if "Sortieren + Reparatur gegen Gewicht zuerst" in s.value]


# ---------------------------------------------------------------------------------------------------
# Methodenvergleich
# ---------------------------------------------------------------------------------------------------
def test_comparison_table_lists_all_strategies_and_the_arrival_row():
    at = fresh()
    df = at.dataframe[0].value
    assert list(df["Verfahren"]) == [C.STRATEGY_LABELS[k] for k in C.STRATEGY_KEYS] + ["Ankunftsreihenfolge (ohne Plan)"]
    assert list(df["Umstauungen"])[:3] == [0, 27, 3] and list(df["Kranspiele"])[:3] == [43, 97, 49] and list(df["Kranzeit (min)"])[:3] == [86, 194, 98]
    assert df.loc[0, "zulässig"] == "nein: Schwerpunkt" and df.loc[1, "zulässig"] == "ja" and df.loc[4, "zulässig"].startswith("nein")
    assert list(df["Differenz zu Gewicht zuerst"])[:3] == [-27, 0, -24]
    assert df.loc[4, "Umstauungen"] > 0 and df.loc[3, "Umstauungen"] == 0


def test_exact_tab_long_run_button_and_stale_key():
    at = fresh()
    assert any("Live mit 4 s Limit" in c.value for c in at.caption)
    click(at, f"🧮 Mit {C.EXACT_LONG_LIMIT_SECONDS} s nachrechnen")
    assert any("Bewiesen optimal" in s.value for s in at.success)
    set_and_run(at, seed_input=5)
    assert any("zuletzt nachgerechnete Ergebnis bezog sich auf ein anderes Szenario" in i.value for i in at.info)


# ---------------------------------------------------------------------------------------------------
# Texte
# ---------------------------------------------------------------------------------------------------
def test_texts_mention_limits_and_no_dead_file_links():
    at = fresh()
    md = "\n".join(m.value for m in at.markdown)
    assert "Grenzen dieses Modells" in md and "Größenordnungen aus einer Simulation" in md and "Kranspiele = Container + 2 × Umstauungen" in md
    assert "Ein Bay, ein Ladehafen" in md and "Reparatur-Heuristik ist meine" in md
    assert "](" not in md.replace("https://sebastianhanisch.net", "")
    for word in ("Umstauung", "Schwerpunkt", "Zielhäfen", "Mathematische Formulierung", "Stabilität"):
        assert word in md
    for ascii_form in ("Staerke", "Zielhaefen", "Stabilitaet", "Gewichtsklasse".replace("k", "kk")):
        assert ascii_form not in md


# ---------------------------------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------------------------------
def test_pdf_download_button_is_in_the_main_view_and_survives_edge_scenarios():
    at = fresh()
    buttons = at.get("download_button")
    assert len(buttons) == 1 and "PDF" in buttons[0].proto.label and buttons[0].proto.url.endswith(".pdf")
    assert not at.sidebar.get("download_button")
    for values in (dict(kg_slider=0), dict(kg_slider=100), dict(tilt_slider=1, n_stacks_slider=4, n_tiers_slider=3, fill_slider=50), dict(n_stacks_slider=12, n_tiers_slider=8)):
        assert len(set_and_run(at, **values).get("download_button")) == 1


def test_pdf_is_built_from_the_curve_only_when_it_matches_the_settings(monkeypatch):
    import stau_pdf_export as PDF
    seen = []
    real = PDF.generate_stau_pdf
    monkeypatch.setattr(PDF, "generate_stau_pdf", lambda *a, **k: seen.append((k.get("sample"), k.get("frontier"))) or real(*a, **k))
    at = set_and_run(fresh(), **SMALL)
    assert seen[-1] == (None, None)                                                     # noch nichts berechnet
    click(at, "📊 Stichprobe und Kurve berechnen")
    assert seen[-1][0] is not None and seen[-1][1] is not None
    set_and_run(at, kg_slider=60)                                                        # andere Einstellung: die alte Kurve gehört nicht ins PDF
    assert seen[-1] == (None, None)
