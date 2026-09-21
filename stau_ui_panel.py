"""Wiederverwendbare Panels: je Verfahren ein Tab im Methodenvergleich und der selbstständige Exakt-Tab (Beweis oder Intervall)."""

import streamlit as st

import stau_constants as C
import stau_evaluation as E
from stau_visualization import bay_figure

VIOLATION_TEXT = {
    "Schwerpunkt": "Die Schwerpunkt-Grenze ist verletzt",
    "Seitenneigung": "Die Seitenneigung ist zu groß",
    "Container": "Es fehlen Container oder es sind zu viele",
    "Höhe": "Ein Stapel ist höher als der Bay",
}


def _delta(value, is_reference):
    return None if is_reference else f"{value:+d}"


def render_strategy_panel(prefix, outcome, outcomes, inst, limits):
    """Beschreibung, Kennzahlen (2 x 2) und Bay-Bild eines Verfahrens. Deltas lesen sich immer als "dieses Verfahren minus Gewicht zuerst" (delta_color="inverse": weniger Umstauungen ist
    besser). Verletzt der Plan eine Grenze, steht das ausdrücklich dabei (nicht vergleichbar). `prefix` macht die Widget-Schlüssel eindeutig."""
    ref = E.outcome_of(outcomes, C.BASELINE)
    st.markdown(C.STRATEGY_DESCRIPTIONS[outcome.key])
    if not outcome.available:
        st.info(outcome.reason)
        return
    is_ref = outcome.key == ref.key
    ev = outcome.evaluation

    top, bottom = st.columns(2), st.columns(2)                      # 2 x 2: vier Spalten schneiden die Namen in schmalen Tabs ab
    m1, m2, m3, m4 = top + bottom
    diff = None if ref.restows is None else outcome.restows - ref.restows
    m1.metric("Umstauungen", f"{outcome.restows}" + ("" if outcome.valid else " ⚠️"), delta=_delta(diff, is_ref) if diff is not None else None,
              delta_color="off" if diff == 0 or not outcome.valid else "inverse", help="Container, die beim Löschen umgestaut werden müssen (je Container zählt jeder Hafen, an dem er im Weg steht).")
    m2.metric("Kranspiele", f"{outcome.moves}", help="Container + 2 × Umstauungen (abheben und zurücksetzen).")
    m3.metric("Schwerpunkt", f"{ev.kg} von {limits.kg_limit}", help=f"Summe Gewicht × Lage; die eingestellte Grenze ist {limits.kg_limit} (tiefstmöglich {limits.kg_min}, Zielhafen-Sortierung {limits.kg_pod}).")
    m4.metric("Seitenneigung", f"{abs(ev.moment)} von {limits.tilt_limit}", help="Betrag des Seitenmoments gegen das zulässige Moment.")
    st.caption(f"Kranzeit {outcome.minutes:.0f} min bei {C.CRANE_MOVES_PER_HOUR} Spielen je Stunde (Annahme).")
    if not outcome.valid:
        st.warning("⚠️ " + "; ".join(VIOLATION_TEXT.get(v, v) for v in outcome.violations) + ": Das Ergebnis ist mit den zulässigen Plänen nicht vergleichbar.")
    st.plotly_chart(bay_figure(inst, outcome.stacks), width="stretch", key=f"{prefix}_bay_chart")


def render_exact_panel(prefix, inst, limits, outcome, long_run=False):
    """Exakt-Tab: Beweislage (bewiesen optimal, Intervall, keine zulässige Stauung), Optimum und Bay-Bild. `long_run` = das Ergebnis stammt aus dem langen Zeitlimit."""
    res = outcome.exact
    limit = C.EXACT_LONG_LIMIT_SECONDS if long_run else C.EXACT_LIVE_LIMIT_SECONDS
    if res.status == "infeasible":
        st.error(outcome.reason)
        return
    if res.status == "unknown":
        st.warning(outcome.reason)
        return
    if res.status == "optimal":
        st.success("✅ Bewiesen optimal" + (" (0 Umstauungen sind die untere Schranke)" if res.value == 0 else "") + f", {res.wall_ms:.0f} ms.")
    else:
        st.warning(f"⏱️ Nicht bewiesen: Nach {limit} s liegt das Optimum zwischen **{res.lower}** und **{res.value}** Umstauungen (beste gefundene Lösung: {res.value}"
                   + ("; Reparatur-Plan, der Löser fand nichts Besseres" if res.source == "Regel" else "") + ").")
    ev = outcome.evaluation
    st.metric("Optimum der Umstauungen" + ("" if res.proven else " (beste bekannte)"), f"{res.value}",
              help="Kleinste Zahl von Umstauungen, die Schwerpunkt-Grenze und Seitenneigung einhält." + ("" if res.proven else " Nicht bewiesen: das Optimum kann kleiner sein."))
    st.caption(f"Schwerpunkt {ev.kg} von {limits.kg_limit}, Seitenneigung {abs(ev.moment)} von {limits.tilt_limit}, Kranspiele {outcome.moves} (Kranzeit {outcome.minutes:.0f} min).")
    st.plotly_chart(bay_figure(inst, outcome.stacks), width="stretch", key=f"{prefix}_bay_chart")
