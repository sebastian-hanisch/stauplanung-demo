"""
Schiffsstauplanung – interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Welle 3 der Hafen-Linie (Schiff -> Kran): Wie stauen wir einen Bay so, dass er stabil steht und in den Anlaufhäfen möglichst wenig umgestaut werden muss?
Die einfachen Regeln sind entweder instabil (nach Zielhafen sortieren) oder teuer (schwer nach unten); gezeigt wird, was die Abwägung wirklich kostet.

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import stau_constants as C
import stau_evaluation as E
import stau_rules as R
import stau_scenario as SC
import stau_visualization as V
from stau_pdf_export import generate_stau_pdf
from stau_presets import (apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, scenario_instance, SETTING_SPECS, sync_query_params)
from stau_ui_panel import render_exact_panel, render_strategy_panel

st.set_page_config(page_title="Schiffsstauplanung – Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)
P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT
LABEL, SHORT = C.STRATEGY_LABELS, {k: v.replace("<br>", " ") for k, v in C.STRATEGY_SHORT.items()}


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_scenario(key):
    """Ladeliste, Grenzen und alle vier Verfahren (Exakt mit kurzem Zeitlimit)."""
    n_stacks, n_tiers, fill_pct, n_ports, seed, kg_pct, tilt_pct = key
    inst = scenario_instance(n_stacks, n_tiers, fill_pct, n_ports, seed)
    lim = SC.limits(inst, kg_pct, tilt_pct)
    return inst, lim, E.run_methods(inst, lim, C.EXACT_LIVE_LIMIT_SECONDS)


@st.cache_data(show_spinner=False, max_entries=8)
def _compute_exact_long(key):
    """Exakt-Tab auf Knopfdruck: langes Zeitlimit."""
    n_stacks, n_tiers, fill_pct, n_ports, seed, kg_pct, tilt_pct = key
    inst = scenario_instance(n_stacks, n_tiers, fill_pct, n_ports, seed)
    return E.exact_outcome(inst, SC.limits(inst, kg_pct, tilt_pct), C.EXACT_LONG_LIMIT_SECONDS)


st.title("🚢 Schiffsstauplanung: Stabil stauen, ohne umzustauen?")
st.markdown(
    """
Ein Schiff wird in einem Hafen beladen und läuft mehrere Häfen an. Was im nächsten Hafen von Bord muss, darf nicht unter dem liegen, was weiter fährt, sonst muss **umgestaut**
werden: abheben, löschen, zurücksetzen. Gleichzeitig muss der Bay **stabil** stehen: Schweres nach unten, die Seiten im Gleichgewicht. Beide Wünsche ziehen in entgegengesetzte
Richtungen. Die Demo zeigt, wie viele Umstauungen die Stabilität wirklich kostet und was einfache Regeln gegen eine gemeinsame Optimierung wert sind. Wie das Modell funktioniert,
steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Herleitung im Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Locker": "Wenn die Grenze nicht drückt, genügt die Zielhafen-Sortierung: 0 Umstauungen, stabil.",
    "Üblich": "Die Zielhafen-Sortierung ist unzulässig, Gewicht zuerst teuer; die Optimierung findet trotzdem einen Plan ohne Umstauungen.",
    "Knapp": "Die Reparatur kostet jetzt etwas, das Optimum nicht: hier lohnt der exakte Löser.",
    "Am Limit": "Die Kante: der Schwerpunkt so tief wie möglich. Jetzt kostet schon das Optimum Umstauungen, und der Beweis dauert; in manchen Ladelisten steht „nicht bewiesen“.",
    "Viele Häfen": "Mehr Anlaufhäfen verschärfen den Zielkonflikt: Gewicht zuerst wird noch teurer.",
}
# Je Zeile drei Schaltflächen: bei fünf in einer Zeile werden die Namen in schmalen Fenstern abgeschnitten.
preset_names = list(C.PRESETS.keys())
for row_start in range(0, len(preset_names), 3):
    row = st.columns(3)
    for col, name in zip(row, preset_names[row_start:row_start + 3]):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_stacks = st.slider("Anzahl Stapel", *bounds("n_stacks_slider"), key="n_stacks_slider", help="Breite des Bays. Stapel x Lagen höchstens 96 (Reichweite des Exakt-Lösers).")
    n_tiers = st.slider("Anzahl Lagen", *bounds("n_tiers_slider"), key="n_tiers_slider", help="Höhe des Bays. Bei nur einer Lage gäbe es keinen Spielraum für den Schwerpunkt.")
    fill_pct = st.slider("Füllgrad (%)", *bounds("fill_slider"), step=C.FILL_PCT_STEP, format="%d%%", key="fill_slider",
                         help="Anteil der Zellen, in denen ein Container steht. Weniger Container geben mehr Freiheit.")
    n_ports = st.slider("Zielhäfen", *bounds("n_ports_slider"), key="n_ports_slider", help="Wie viele Häfen das Schiff nach dem Ladehafen anläuft. Mehr Häfen = mehr Ordnungszwang.")
    seed = st.number_input("Seed der Ladeliste", *bounds("seed_input"), key="seed_input", step=1, help="Bestimmt Zielhäfen und Gewichtsklassen der Container.")
    st.caption(f"= {SC.n_boxes(n_stacks, n_tiers, fill_pct)} Container in {n_stacks * n_tiers} Zellen")

    st.markdown("**Stabilität**")
    kg_pct = st.slider("Schwerpunkt-Grenze (% des Spielraums)", *bounds("kg_slider"), step=C.KG_PCT_STEP, format="%d%%", key="kg_slider",
                       help="100 % = die Zielhafen-Sortierung ist gerade noch erlaubt, 0 % = nur der tiefstmögliche Schwerpunkt. Unter etwa 15 % rechnet der Exakt-Löser lang "
                       "und beweist das Optimum oft nicht.")
    tilt_pct = st.slider("Seitenneigung (% des größten Moments)", *bounds("tilt_slider"), format="%d%%", key="tilt_slider",
                         help="Zulässige Schieflage. Mindestens 1 %: Bei 0 gibt es praktisch keinen zulässigen Plan.")
    st.button("🎲 Neue Ladeliste", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed für die Ladeliste.")

sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

bay = (int(n_stacks), int(n_tiers), int(fill_pct), int(n_ports))
scenario_key = bay + (int(seed), int(kg_pct), int(tilt_pct))

with st.spinner("Führe die Verfahren aus (Exakt bis zu %d s)..." % C.EXACT_LIVE_LIMIT_SECONDS):
    inst, lim, outcomes = _compute_scenario(scenario_key)
by_key = {o.key: o for o in outcomes}
ref = by_key[W_]
n_boxes = len(inst.boxes)


def _restow_text(o):
    """Wert der Kennzahl: Umstauungen, mit ⚠️ bei verletzter Grenze, mit ≤ bei nicht bewiesenem Optimum, – ohne Plan."""
    if not o.available:
        return "–"
    txt = f"{o.restows}"
    if o.key == X_ and not o.exact.proven:
        txt = f"≤ {txt}"
    return txt + ("" if o.valid else " ⚠️")


# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🎯 Was kostet die Stabilität in diesem Bay?")
st.caption("Umstauungen der Ladeliste: wie viele Container beim Löschen abgehoben und zurückgesetzt werden müssen (je Hafen, an dem sie im Weg stehen). Alle Verfahren stauen "
           "dieselben Container.")

metric_rows = [st.columns(2), st.columns(2)]                  # 2 x 2: vier Spalten schneiden die Namen bei 800 px ab
for col, o in zip(metric_rows[0] + metric_rows[1], outcomes):
    if not o.available:
        col.metric(o.label, "–", help=o.reason)
        continue
    diff = o.restows - ref.restows if ref.restows is not None else None
    same = diff == 0
    help_txt = "Referenz für alle Vergleiche." if o.key == W_ else "Differenz: dieses Verfahren minus Gewicht zuerst (weniger Umstauungen ist besser)."
    if not o.valid:
        help_txt += " ⚠️ Der Plan verletzt eine Grenze (" + ", ".join(o.violations) + "): nicht mit den zulässigen Plänen vergleichbar."
    if o.key == X_ and not o.exact.proven:
        help_txt += f" Nicht bewiesen: das Optimum liegt zwischen {o.exact.lower} und {o.exact.value}."
    col.metric(o.label, _restow_text(o), delta=None if o.key == W_ else ("0" if same else f"{diff:+d}"), delta_color="off" if same or not o.valid else "inverse", help=help_txt)         # ein Plan, der eine Grenze verletzt, gilt nicht als "besser"

exact_res = by_key[X_].exact
if exact_res.status == "infeasible":
    st.error("⛔ " + by_key[X_].reason)
else:
    best = by_key[X_] if by_key[X_].available else by_key[R_]
    saved = ref.minutes - best.minutes if best.valid and ref.valid else None
    st.info(
        f"ℹ️ Kranspiele = {n_boxes} Container + 2 × Umstauungen. Gewicht zuerst braucht **{ref.moves} Spiele** ({ref.minutes:.0f} min bei {C.CRANE_MOVES_PER_HOUR} Spielen je Stunde), "
        f"{SHORT[best.key]} **{best.moves}** ({best.minutes:.0f} min)"
        + (f": **{saved:.0f} min** weniger Kranzeit für diesen Bay." if saved is not None and saved > 0 else ".")
        + (" Zielhafen zuerst verletzt die Schwerpunkt-Grenze und zählt deshalb nicht." if not by_key[P_].valid else "")
    )

st.markdown("#### 🔍 Blick ins Bay")
right_key = st.radio("Rechts vergleichen mit", list(C.RIGHT_VIEW_KEYS), format_func=LABEL.get, key="view_radio", horizontal=True, help="Links steht immer Gewicht zuerst.")
right = by_key[right_key]
left_col, right_col = st.columns(2)
for col, o, side in ((left_col, ref, "left"), (right_col, right, "right")):
    with col:
        st.markdown(f"**{o.label}**")
        if o.available:
            st.plotly_chart(V.bay_figure(inst, o.stacks, legend=False), width="stretch", key=f"bay_chart_{side}")
        else:
            st.info(o.reason)
port_colors = ", ".join(f"{p + 1} {C.POD_COLOR_NAMES[p]}" for p in range(inst.n_ports))
st.caption(f"Ein Rechteck je Container: Farbe = Zielhafen ({port_colors}), Zahl = Gewichtsklasse (dunkler = schwerer), **roter Rand = muss umgestaut werden**. Lage 1 ist unten. "
           f"Schwerpunkt-Grenze: tiefstmöglich {lim.kg_min}, eingestellt {lim.kg_limit}, Zielhafen-Sortierung {lim.kg_pod}; zulässiges Seitenmoment {lim.tilt_limit}.")

pdf_slot = st.container()          # der Download steht in der Hauptansicht, wird aber erst gefüllt, wenn Stichprobe und Kurve (falls berechnet) feststehen

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.subheader("📐 Was kostet die Stabilität?")
st.markdown(
    """
Kernfrage dieser Demo: Wie viele Umstauungen kostet ein stabiler Stauplan, und lohnt sich dafür ein exakter Löser? Die einfachen Regeln sind entweder **instabil** (nach Zielhafen
sortieren: 0 Umstauungen, aber der Schwerpunkt liegt zu hoch) oder **teuer** (schwer nach unten: stabil, aber ohne Rücksicht auf die Häfen). Wer beides zugleich optimiert, zahlt
bis fast zur Grenze des Möglichen nichts; erst ganz am strengen Ende der Schwerpunkt-Grenze entstehen einzelne Umstauungen (**die Kante**). Hier live für Ihre Einstellungen
gerechnet, **mit der Verteilung dazu**:
"""
)
g1, g2, g3 = st.columns(3)
g1.metric("Tiefstmöglicher Schwerpunkt", f"{lim.kg_min}", help="Summe Gewicht × Lage, wenn die schwersten Container ganz unten stehen (Gewicht zuerst).")
g2.metric("Eingestellte Grenze", f"{lim.kg_limit}", help=f"{kg_pct} % des Spielraums zwischen dem tiefstmöglichen Schwerpunkt und dem der Zielhafen-Sortierung.")
g3.metric("Zielhafen-Sortierung", f"{lim.kg_pod}", help="Schwerpunkt, wenn nach Zielhafen sortiert wird (0 Umstauungen): erlaubt erst bei 100 %.")

curve_key = bay + (int(tilt_pct),)
sample_key = bay + (int(kg_pct), int(tilt_pct))
pts, n_lists = E.frontier_plan(bay[0], bay[1])
st.caption(
    f"Die Stichprobe rechnet {C.SAMPLE_LISTS} Ladelisten mit Ihren Einstellungen, die Kurve {len(pts)} Grenzwerte × {n_lists} Ladelisten, jeweils mit {C.SAMPLE_LIMIT_SECONDS} s Limit für den exakten "
    "Löser. Das dauert je nach Bay-Größe etwa 15 bis 90 Sekunden und läuft deshalb auf Knopfdruck. Beides hängt nicht vom eingestellten Seed ab."
)
if st.button("📊 Stichprobe und Kurve berechnen", key="stau_curve_btn"):
    bar = st.progress(0.0, text="Rechne die Stichprobe ...")
    try:
        sample_new = E.sample(*bay, int(kg_pct), int(tilt_pct), progress=lambda f: bar.progress(min(1.0, 0.4 * f), text=f"Rechne die Stichprobe ... {f * 100:.0f} %"))
        frontier_new = E.frontier(*bay, int(tilt_pct), progress=lambda f: bar.progress(min(1.0, 0.4 + 0.6 * f), text=f"Rechne die Kurve ... {f * 100:.0f} %"))
        st.session_state["stau_curve"] = (sample_key, curve_key, sample_new, frontier_new)
    except ValueError as err:
        st.warning(f"Die Berechnung ist mit diesen Einstellungen nicht möglich: {err}")
    bar.empty()


def _show_verdict(sample, label, key, reference):
    v = E.verdict(sample, key, reference)
    d = E.distribution(sample, key, reference)
    if v.kind == "none":
        st.info(f"ℹ️ **{label}**: In keiner Ladeliste sind beide Verfahren zulässig, ein Vergleich ist nicht möglich.")
    elif v.kind == "better":
        amount = f"**{abs(v.pct):.0f} % weniger**" if v.pct is not None else f"**{-v.diff:.1f} weniger**"
        st.success(f"✅ **{label}**: im Mittel {amount} Umstauungen ({-v.diff:.1f} je Ladeliste, Standardfehler {v.se:.2f}). In **{d.worse * 100:.0f} %** der Ladelisten ist es umgekehrt.")
    elif v.kind == "worse":
        amount = f"**{v.pct:.0f} % mehr**" if v.pct is not None else f"**{v.diff:.1f} mehr**"
        st.warning(f"⚠️ **{label}**: im Mittel {amount} Umstauungen ({v.diff:.1f} je Ladeliste, Standardfehler {v.se:.2f}). In **{d.better * 100:.0f} %** der Ladelisten ist es besser.")
    else:
        st.info(f"ℹ️ Kein klarer Unterschied bei **{label}**: die Differenz ({v.diff:+.1f} je Ladeliste) liegt innerhalb des Rauschens (Standardfehler {v.se:.2f}). "
                f"Besser in {d.better * 100:.0f} %, schlechter in {d.worse * 100:.0f} % der Ladelisten.")


stored = st.session_state.get("stau_curve")
if stored is not None and stored[0] == sample_key and stored[1] == curve_key:
    sample, frontier = stored[2], stored[3]
    st.markdown("**Urteil über die Stichprobe** (gepaarte Differenz, klar ab mehr als zwei Standardfehlern; nur Listen, in denen beide Verfahren zulässig sind)")
    _show_verdict(sample, "Exakt gegen Gewicht zuerst", X_, W_)
    _show_verdict(sample, "Exakt gegen Sortieren + Reparatur", X_, R_)
    _show_verdict(sample, "Sortieren + Reparatur gegen Gewicht zuerst", R_, W_)
    dists = [E.distribution(sample, k, W_) for k in (R_, X_)]
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown("**Wie sich die Gewinne verteilen** (Anteil der Ladelisten)")
        st.plotly_chart(V.distribution_figure(dists), width="stretch", key="distribution_chart")
    with dcol2:
        st.markdown("**Typische Liste gegen Mittelwert**")
        st.plotly_chart(V.gain_figure(dists), width="stretch", key="gain_chart")
    valid_pod = E.valid_share(sample, P_) * 100
    st.caption(
        f"Basis: {len(sample)} Ladelisten (Seeds 0-{len(sample) - 1}, nicht Ihr Seed). Zielhafen zuerst ist in {valid_pod:.0f} % der Listen zulässig, deshalb fehlt er im Urteil und in den Balken. "
        f"Gewicht zuerst im Mittel {E.mean_restows(sample, W_) or 0:.1f}, Reparatur {E.mean_restows(sample, R_) or 0:.1f}, Exakt {E.mean_restows(sample, X_) or 0:.1f} Umstauungen. "
        f"Gleich heißt: dieselbe Zahl. In {E.unproven_count(sample)} von {len(sample)} Listen ist Exakt nicht bewiesen; der Wert ist dort eine Obergrenze des Optimums."
    )
    st.markdown("**Umstauungen über der Schwerpunkt-Grenze (die Frontier)**")
    st.plotly_chart(V.frontier_figure(frontier, int(kg_pct) if int(kg_pct) in frontier.points else None), width="stretch", key="frontier_chart")
    kante = E.kante(frontier)
    st.caption(
        f"Basis: {len(frontier.points)} Grenzwerte × {frontier.n_lists} Ladelisten (Seeds 0-{frontier.n_lists - 1}), Seitenneigung {frontier.tilt_pct} %. Ein gefüllter grüner Punkt heißt: Optimum in allen "
        "Listen bewiesen; ein offener: in mindestens einer Liste nur die beste gefundene Lösung (Obergrenze). Gewicht zuerst hängt nicht von der Grenze ab; Zielhafen zuerst ist nur bei 100 % zulässig. "
        + (f"Ab einer Grenze von {kante} % abwärts kostet auch das Optimum im Mittel mehr als eine halbe Umstauung." if kante is not None else "Im untersuchten Bereich kostet auch das Optimum im Mittel höchstens eine halbe Umstauung.")
    )
elif stored is not None:
    st.info("ℹ️ Die zuletzt berechnete Stichprobe und Kurve bezogen sich auf andere Einstellungen. Erneut auf '📊 Stichprobe und Kurve berechnen' klicken.")
else:
    st.info("Noch nichts berechnet – auf den Button oben klicken.")

with pdf_slot:
    have = stored is not None and stored[0] == sample_key and stored[1] == curve_key
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_stau_pdf(inst, lim, outcomes, dict(n_stacks=bay[0], n_tiers=bay[1], fill_pct=bay[2], n_ports=bay[3], seed=int(seed), kg_pct=int(kg_pct), tilt_pct=int(tilt_pct)),
                               sample=stored[2] if have else None, frontier=stored[3] if have else None),
        file_name="stauplanung_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Szenario, Verfahrensvergleich und, falls berechnet, Stichprobe mit Urteil und die Kurve über der Schwerpunkt-Grenze.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Methodenvergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tabs = st.tabs([o.label for o in outcomes] + ["📊 Vergleich"])
    for tab, outcome in zip(tabs, outcomes):
        with tab:
            if outcome.key == X_:
                long_key = st.session_state.get("stau_exact_long_key")
                st.caption("Die kleinste Zahl von Umstauungen, die beide Grenzen einhält (CP-SAT). Ein Optimum von 0 ist per Definition bewiesen; sonst steht ein Intervall aus unterer Schranke "
                           f"und bester Lösung. Live mit {C.EXACT_LIVE_LIMIT_SECONDS} s Limit, hier auf Knopfdruck mit {C.EXACT_LONG_LIMIT_SECONDS} s.")
                if st.button(f"🧮 Mit {C.EXACT_LONG_LIMIT_SECONDS} s nachrechnen", key="stau_exact_btn"):
                    st.session_state["stau_exact_long_key"] = scenario_key
                    long_key = scenario_key
                if long_key == scenario_key:
                    with st.spinner(f"Exakte Suche (bis zu {C.EXACT_LONG_LIMIT_SECONDS} s)..."):
                        long_outcome = _compute_exact_long(scenario_key)
                    render_exact_panel("exact", inst, lim, long_outcome, long_run=True)
                else:
                    if long_key is not None:
                        st.info("ℹ️ Das zuletzt nachgerechnete Ergebnis bezog sich auf ein anderes Szenario. Erneut auf den Knopf klicken; gezeigt ist das Live-Ergebnis.")
                    render_exact_panel("exact", inst, lim, outcome)
            else:
                render_strategy_panel(f"strategy_{outcome.key}", outcome, outcomes, inst, lim)
    with tabs[4]:
        rows = E.comparison_rows(outcomes)
        arrival_ev = R.evaluate(inst, R.arrival(inst), lim)
        table = []
        for r in rows:
            if r.available:
                table.append({"Verfahren": r.label, "Umstauungen": r.restows, "Kranspiele": r.moves, "Kranzeit (min)": round(r.minutes), "Schwerpunkt": f"{r.kg} von {lim.kg_limit}",
                              "Seitenmoment": f"{abs(r.moment)} von {lim.tilt_limit}", "zulässig": "ja" if r.valid else "nein: " + ", ".join(r.violations),
                              "Differenz zu Gewicht zuerst": r.delta_vs_baseline})
            else:
                table.append({"Verfahren": r.label, "zulässig": "kein Plan: " + r.reason})
        table.append({"Verfahren": "Ankunftsreihenfolge (ohne Plan)", "Umstauungen": arrival_ev.restows, "Kranspiele": E.crane_moves(n_boxes, arrival_ev.restows),
                      "Kranzeit (min)": round(E.crane_minutes(E.crane_moves(n_boxes, arrival_ev.restows))), "Schwerpunkt": f"{arrival_ev.kg} von {lim.kg_limit}",
                      "Seitenmoment": f"{abs(arrival_ev.moment)} von {lim.tilt_limit}", "zulässig": "ja" if arrival_ev.valid else "nein: " + ", ".join(arrival_ev.violations),
                      "Differenz zu Gewicht zuerst": arrival_ev.restows - ref.restows})
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)
        st.plotly_chart(V.comparison_figure(outcomes), width="stretch", key="comparison_chart")
        st.caption("Die Ankunftsreihenfolge (jeder Container in der Reihenfolge der Ladeliste auf den niedrigsten Stapel) ist der Alltag ohne Plan und dient nur als Vergleich.")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Bay und Container.** Ein Bay besteht aus Stapeln nebeneinander mit mehreren Lagen übereinander. Jeder Container hat einen **Zielhafen** (in welchem Hafen er von Bord geht, die Häfen
werden nacheinander angelaufen) und eine **Gewichtsklasse** von 1 (leicht) bis 4 (schwer). Alle Container sind gleich groß und stehen ohne Lücken auf dem Container darunter.

**Umstauung.** Liegt ein Container für Hafen 3 über einem für Hafen 1, muss er beim Löschen in Hafen 1 abgehoben und wieder aufgesetzt werden: eine Umstauung. Stehen darunter Container
für Hafen 1 und Hafen 2, wird er an beiden Häfen umgestaut (zweimal gezählt). Jede Umstauung kostet zwei Kranspiele (abheben, zurücksetzen): **Kranspiele = Container + 2 × Umstauungen**.

**Stabilität.** Zwei Grenzen müssen halten. Die **Schwerpunkt-Grenze** begrenzt Σ Gewicht × Lage: Schweres muss weit unten stehen. Sie ist als Anteil des Spielraums zwischen dem
tiefstmöglichen Schwerpunkt (schwerste Container zuunterst) und dem der Zielhafen-Sortierung angegeben: 100 % erlaubt die Zielhafen-Sortierung gerade noch, 0 % nur den tiefsten
Schwerpunkt. Die **Seitenneigung** begrenzt das Moment Σ (Abstand von der Mitte) × Stapelgewicht: links und rechts muss ähnlich viel Gewicht stehen.

**Vier Verfahren**, alle mit denselben Containern:

- **Zielhafen zuerst**: nach Zielhafen sortiert, der fernste unten. Null Umstauungen, aber der Schwerpunkt liegt so hoch wie möglich; unter 100 % Grenze ist der Plan unzulässig.
- **Gewicht zuerst** (Referenz): schwerste unten. Stabil, aber ohne Rücksicht auf die Häfen: viele Umstauungen.
- **Sortieren + Reparatur**: Start bei der Zielhafen-Sortierung, dann Tausche, die den Schwerpunkt unter die Grenze bringen und dabei möglichst wenig Umstauungen kosten. Kann die Grenze in
  seltenen Fällen verfehlen (dann steht "Grenze verletzt").
- **Exakt (CP-SAT)**: die kleinste Zahl von Umstauungen, die beide Grenzen einhält, mit Beweis. Reicht das Zeitlimit nicht, steht ein Intervall aus unterer Schranke und bester Lösung, nie ein
  unbewiesener Wert als Optimum. Ein Optimum von 0 ist per Definition bewiesen.

**Das Bay-Bild lesen.** Ein Rechteck je Container: Farbe = Zielhafen, Zahl = Gewichtsklasse (dunkler = schwerer), **roter Rand = dieser Container muss umgestaut werden**. Unten ist Lage 1.

**Warum die einfachen Regeln scheitern und die Abwägung fast nichts kostet.** Nach Zielhafen sortiert steht jeder Stapel von unten nach oben in absteigender Hafenreihenfolge, aber die Gewichte
sind zufällig verteilt: Der Schwerpunkt liegt hoch. Nach Gewicht sortiert liegt er tief, aber die Häfen sind durcheinander. Die Anordnung dazwischen gibt es: Jeder Stapel bleibt nach
Zielhafen geordnet, und die schweren Container werden auf die unteren Lagen möglichst vieler Stapel verteilt. Das gelingt fast immer ohne Umstauung; erst wenn die Grenze so streng wird,
dass fast alle schweren Container ganz unten stehen müssen (die **Kante**), bleiben Umstauungen. Dass das Optimum das kann und eine einfache Reparatur oft knapp danebenliegt, zeigen die
Stichprobe und die Kurve.

**Stichprobe, Verteilung und Urteil.** Die Stichprobe stellt Ihre Einstellungen auf 20 Ladelisten (Seeds 0 bis 19, nicht Ihr Seed) nach. Ein Unterschied gilt als klar, wenn er mehr als zwei
Standardfehler der gepaarten Differenz beträgt. Die Verteilung zeigt, in wie vielen Listen ein Verfahren besser, gleich oder schlechter ist als Gewicht zuerst; ein Mittelwert weit vom Median
heißt, dass wenige Listen den Gewinn tragen.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- **Ein Bay, ein Ladehafen**: kein Zu- und Aussteigen unterwegs, keine Kranverteilung über mehrere Bays.
- Der **Schwerpunkt ist die Summe Gewicht × Lage**, nicht die Längs- und Quer-Rechnung eines ganzen Schiffs; die Seitenneigung ein einfaches Moment.
- **Nicht modelliert**: Reefer-Steckdosen, 20/40 Fuß, Gefahrgut-Trennung, Lukendeckel, Stapelgewichtsgrenze.
- Gewichtsklassen und Zielhäfen sind **gleichverteilt und unabhängig**; die **Reparatur-Heuristik ist meine**, eine bessere könnte die Lücke zum Optimum schließen.
- **Kranspiele je Stunde** (30) sind eine Annahme; die Kranzeit ist eine Umrechnung, keine Messung.
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an echten Bay-Plänen.**
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Stauplanung eines Bays mit Zielhäfen, Schwerpunkt und Seitenneigung** (NP-schwer; kleine Fälle exakt lösbar).

Gegeben sind $C$ Stapel, $T$ Lagen und Container-Typen $k$ mit Zielhafen $p_k \in \{1, \dots, P\}$, Gewichtsklasse $w_k \in \{1, \dots, 4\}$ und Anzahl $n_k$. Variable
$x_{c,t,k} \in \{0,1\}$: Ein Container vom Typ $k$ steht in Stapel $c$, Lage $t$ (Lage $0$ unten).

**Aufbau:**
$$
\sum_k x_{c,t,k} \le 1, \qquad \sum_k x_{c,t,k} \le \sum_k x_{c,t-1,k}, \qquad \sum_{c,t} x_{c,t,k} = n_k .
$$

**Schwerpunkt und Seitenneigung** mit Stapelgewicht $W_c = \sum_{t,k} w_k x_{c,t,k}$:
$$
\sum_{c,t,k} w_k \, t \; x_{c,t,k} \le L, \qquad \Big| \sum_c (2c - C + 1)\, W_c \Big| \le B .
$$
$L$ liegt bei $\theta \cdot 100\,\%$ des Spielraums zwischen dem Schwerpunkt der nach Gewicht sortierten ($K_{\min}$) und der nach Zielhafen sortierten ($K_{\mathrm{pod}}$) Ladeliste,
$L = K_{\min} + \lfloor \theta \, (K_{\mathrm{pod}} - K_{\min}) \rfloor$; $B$ ist ein Anteil des größten Moments $(C-1) \sum_j w_j$.

**Umstauungen.** Container $j$ in Lage $t$ wird an Hafen $p < p_j$ umgestaut, wenn unter ihm ein Container mit Zielhafen $p$ steht. Mit $b_{c,t,p} = 1$, wenn unter Lage $t$ ein Container mit
Zielhafen $p$ steht, und $r_{c,t,p} \ge b_{c,t,p} + [\,p_{j(c,t)} > p\,] - 1$:
$$
\min \sum_{c,t,p} r_{c,t,p} .
$$
Ein Wert von $0$ ist bewiesen optimal, da die Zielfunktion nicht negativ ist.

**Vergleich über Ladelisten.** Für Verfahren $A$ gegen die Referenz $B$ auf denselben Ladelisten $\ell = 1, \dots, S$ (beide zulässig) ist $\Delta_\ell = r_B^{(\ell)} - r_A^{(\ell)}$ der Gewinn;
berichtet werden Mittel, Median und die Anteile der Listen mit $\Delta_\ell > 0$ (besser), $= 0$ (gleich), $< 0$ (schlechter). Ein Unterschied gilt als klar, wenn $|\bar\Delta| > 2\,\mathrm{SE}(\Delta)$
mit dem Standardfehler der gepaarten Differenz.

Implementiert in `stau_rules.py` (Bewertung und Regeln), `stau_exact.py` (CP-SAT) und `stau_evaluation.py` (Vergleiche).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
