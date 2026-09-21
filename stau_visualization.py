"""Plotly-Diagramme: Bay-Bild, Frontier-Kurve, Verteilung der Gewinne, Vergleich.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Markerlinien in mittlerem Grau, neutrale Flächen halbtransparent (nichts Weißes im dunklen
Schema), Überschriften stehen als Markdown ÜBER dem Diagramm (eine umbrechende Legende überdeckt sonst den Plotly-Titel auf dem Handy). Alle Funktionen sind reine Rechnung auf den
Ergebnisobjekten; Streamlit kommt hier nicht vor."""

import stau_constants as C
import stau_evaluation as E
import stau_rules as R

LEGEND_TOP = dict(orientation="h", yanchor="bottom", y=1.02, x=0)
LEGEND_BOTTOM = dict(orientation="h", yanchor="top", y=-0.22, x=0)
CELL_PAD = 0.05                     # Abstand zwischen Containern (in Zellbreiten)


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _pod_color(pod):
    return C.POD_COLORS[(pod - 1) % len(C.POD_COLORS)]


def _hover_points(x0, x1, y0, y1, nx=3, ny=3):
    """Unsichtbare Punkte über das ganze Rechteck: Plotly hovert Spuren nach dem nächsten DATENPUNKT, ein einzelner Mittelpunkt träfe nur die Mitte."""
    xs = [x0 + (x1 - x0) * (a + 0.5) / nx for a in range(nx)]
    ys = [y0 + (y1 - y0) * (b + 0.5) / ny for b in range(ny)]
    return [x for _ in ys for x in xs], [y for y in ys for _ in xs]


def _restow_ports(stack, t):
    """Zielhäfen unter Lage t, die kleiner als der Zielhafen des Containers sind (an diesen Häfen muss er umgestaut werden)."""
    pod = stack[t][0]
    return sorted({p for p, _ in stack[:t] if p < pod})


def bay_figure(inst, stacks, legend=True):
    """Ein Bay: Zellen (Stapel nebeneinander, Lage 0 unten). Farbe = Zielhafen, Zahl = Gewichtsklasse (dunkler = schwerer), roter Rand = muss umgestaut werden. Leere Zellen sind grau
    hinterlegt. Hover über das ganze Container-Rechteck."""
    import plotly.graph_objects as go

    n_c, n_t = inst.n_stacks, inst.n_tiers
    fig = go.Figure()
    for c in range(n_c):
        for t in range(n_t):
            fig.add_shape(type="rect", x0=c + CELL_PAD, x1=c + 1 - CELL_PAD, y0=t + CELL_PAD, y1=t + 1 - CELL_PAD, fillcolor=C.EMPTY_CELL_COLOR, line=dict(width=0), layer="below")
    hx, hy, htext, lx, ly, ltext = [], [], [], [], [], []
    for c, stack in enumerate(stacks):
        blocked = R.blockers(stack)
        for t, (pod, w) in enumerate(stack):
            red = t in blocked
            fig.add_shape(type="rect", x0=c + CELL_PAD, x1=c + 1 - CELL_PAD, y0=t + CELL_PAD, y1=t + 1 - CELL_PAD, fillcolor=_pod_color(pod), opacity=0.5 + 0.12 * w,
                          line=dict(color=C.RESTOW_COLOR if red else "rgba(128,136,149,0.5)", width=3 if red else 1), layer="below")
            px, py = _hover_points(c + CELL_PAD, c + 1 - CELL_PAD, t + CELL_PAD, t + 1 - CELL_PAD)
            text = f"<b>Zielhafen {pod}</b>, Gewichtsklasse {w}<br>Stapel {c + 1}, Lage {t + 1}"
            if red:
                text += "<br><b>muss umgestaut werden</b> an Hafen " + ", ".join(str(p) for p in _restow_ports(stack, t))
            hx += px
            hy += py
            htext += [text] * len(px)
            lx.append(c + 0.5)
            ly.append(t + 0.5)
            ltext.append(str(w))
    fig.add_trace(go.Scatter(x=hx, y=hy, mode="markers", marker=dict(size=14, opacity=0), showlegend=False, text=htext, hovertemplate="%{text}<extra></extra>", name="Container"))
    fig.add_trace(go.Scatter(x=lx, y=ly, mode="text", text=ltext, textfont=dict(color="white", size=12), showlegend=False, hoverinfo="skip", name="Gewichtsklassen"))
    if legend:
        present = sorted({pod for s in stacks for pod, _ in s})
        for pod in present:
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=f"Hafen {pod}", marker=dict(size=12, symbol="square", color=_pod_color(pod))))
        if any(R.blockers(s) for s in stacks):
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Umstauer", marker=dict(size=12, symbol="square-open", color=C.RESTOW_COLOR, line=dict(width=2))))
    fig.update_layout(template="plotly_white", height=90 + 40 * n_t + (40 if legend else 0), legend=LEGEND_TOP, showlegend=legend, margin=dict(t=50 if legend else 10, b=40, l=40, r=10),
                      hovermode="closest", xaxis_title="Stapel", yaxis_title="Lage")
    fig.update_xaxes(range=[-0.02, n_c + 0.02], tickmode="array", tickvals=[c + 0.5 for c in range(n_c)], ticktext=[str(c + 1) for c in range(n_c)], showgrid=False, zeroline=False)
    fig.update_yaxes(range=[-0.02, n_t + 0.02], tickmode="array", tickvals=[t + 0.5 for t in range(n_t)], ticktext=[str(t + 1) for t in range(n_t)], showgrid=False, zeroline=False)
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Frontier
# ---------------------------------------------------------------------------------------------------
def frontier_figure(fr, kg_current=None):
    """Umstauungen über der Schwerpunkt-Grenze (Mittel über die Ladelisten mit zulässigem Plan). Exakt: gefüllter Punkt = in allen Listen bewiesen, offener Punkt = in mindestens einer Liste nur
    beste Lösung (Obergrenze des Optimums). Zielhafen zuerst erscheint nur, wo er zulässig ist. Gepunktete graue Linie = eingestellte Grenze."""
    import plotly.graph_objects as go

    fig = go.Figure()
    proven = E.curve_proven(fr)
    for key in (C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT, C.STRAT_POD):
        means, shares = E.curve(fr, key), E.curve_valid_share(fr, key)
        idx = [i for i, m in enumerate(means) if m is not None]
        if not idx:
            continue
        color, label = C.STRATEGY_COLORS[key], C.STRATEGY_LABELS[key]
        x = [fr.points[i] for i in idx]
        y = [means[i] for i in idx]
        if key == C.STRAT_EXACT:
            symbols = ["circle" if proven[i] == 1 else "circle-open" for i in idx]
            hover = [f"<b>{label}</b><br>Grenze {fr.points[i]} %<br>{means[i]:.2f} Umstauungen im Mittel<br>bewiesen in {proven[i] * 100:.0f} % der Listen" for i in idx]
        else:
            symbols = ["circle"] * len(idx)
            hover = [f"<b>{label}</b><br>Grenze {fr.points[i]} %<br>{means[i]:.2f} Umstauungen im Mittel<br>zulässig in {shares[i] * 100:.0f} % der Listen" for i in idx]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers" if len(idx) > 1 else "markers", name=label, line=dict(color=color, width=2.5), text=hover, hovertemplate="%{text}<extra></extra>",
                                 marker=dict(size=8, symbol=symbols, color=color, line=dict(color=color, width=2))))
    if kg_current is not None:
        fig.add_vline(x=kg_current, line=dict(color=C.MARKER_LINE_COLOR, width=2, dash="dot"), annotation_text="eingestellt", annotation_position="top", annotation_font=dict(size=11))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT + 20, legend=LEGEND_BOTTOM, margin=dict(t=30, b=120), hovermode="closest",
                      xaxis_title="Schwerpunkt-Grenze (% des Spielraums)", yaxis_title="Umstauungen (Mittel)")
    fig.update_xaxes(range=[min(fr.points) - 4, max(fr.points) + 4], tickmode="array", tickvals=list(fr.points))
    fig.update_yaxes(rangemode="tozero")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Verteilung der Gewinne, Vergleich
# ---------------------------------------------------------------------------------------------------
def distribution_figure(dists):
    """Je Verfahren ein gestapelter Balken: Anteil der Ladelisten, in denen es gegen Gewicht zuerst besser / gleich / schlechter abschneidet (nur Listen, in denen beide zulässig sind)."""
    import plotly.graph_objects as go

    labels = [C.STRATEGY_SHORT[d.key].replace("<br>", " ") for d in dists]
    fig = go.Figure()
    for attr, name in (("better", "besser als Gewicht zuerst"), ("equal", "gleich"), ("worse", "schlechter als Gewicht zuerst")):
        shares = [getattr(d, attr) * 100 for d in dists]
        fig.add_trace(go.Bar(y=labels, x=shares, orientation="h", name=name, marker_color=C.OUTCOME_COLORS[attr], text=[f"{v:.0f} %" if v >= 6 else "" for v in shares],
                             textposition="inside", insidetextanchor="middle", hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.0f}} % der Ladelisten<extra></extra>"))
    fig.update_layout(barmode="stack", template="plotly_white", height=150 + 70 * len(dists), legend=dict(LEGEND_BOTTOM, y=-0.45, traceorder="normal"), margin=dict(t=20, b=110, l=10),
                      xaxis_title="Anteil der Ladelisten (%)")
    fig.update_xaxes(range=[0, 100])
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


def gain_figure(dists):
    """Median-Gewinn neben Mittel-Gewinn je Verfahren (Umstauungen je Ladeliste, positiv = weniger als Gewicht zuerst): ein Mittelwert weit vom Median heißt, dass wenige Listen tragen."""
    import plotly.graph_objects as go

    labels = [C.STRATEGY_SHORT[d.key] for d in dists]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[d.median_gain for d in dists], name="Median (typische Liste)", marker_color="#2a6fb0", hovertemplate="<b>%{x}</b><br>Median-Gewinn %{y:.1f}<extra></extra>"))
    fig.add_trace(go.Bar(x=labels, y=[d.mean_gain for d in dists], name="Mittelwert", marker_color="#c77700", hovertemplate="<b>%{x}</b><br>Mittel-Gewinn %{y:.1f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=C.MARKER_LINE_COLOR, width=1))
    fig.update_layout(barmode="group", template="plotly_white", height=C.CHART_HEIGHT - 60, legend=LEGEND_BOTTOM, margin=dict(t=20, b=100), yaxis_title="Gewinn (Umstauungen je Liste)")
    return _lock_axes(fig)


def comparison_figure(outcomes):
    """Zwei Blicke auf dieselbe Ladeliste: Umstauungen und Kranspiele je Verfahren. Schraffierte Balken verletzen eine Grenze (nicht vergleichbar); Verfahren ohne Plan stehen mit „–“."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Umstauungen", "Kranspiele (Container + 2 × Umstauungen)"), horizontal_spacing=0.14)
    labels = [C.STRATEGY_SHORT[o.key] + ("" if o.available else "<br>–") for o in outcomes]
    for col, attr in ((1, "restows"), (2, "moves")):
        for label, o in zip(labels, outcomes):
            if not o.available:
                continue
            fig.add_trace(go.Bar(x=[label], y=[getattr(o, attr)], marker=dict(color=C.STRATEGY_COLORS[o.key], pattern_shape="" if o.valid else "/", line=dict(color=C.MARKER_LINE_COLOR, width=1)),
                                 showlegend=False, text=[str(getattr(o, attr))], textposition="outside",
                                 hovertemplate=f"<b>{o.label}</b><br>%{{y}}" + ("" if o.valid else "<br>verletzt: " + ", ".join(o.violations)) + "<extra></extra>"), row=1, col=col)
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT - 40, margin=dict(t=40, b=60), barmode="overlay")
    fig.update_xaxes(tickangle=0, tickfont=dict(size=10), categoryorder="array", categoryarray=labels)
    fig.update_yaxes(rangemode="tozero")
    if any(not o.valid for o in outcomes if o.available):
        fig.add_annotation(text="Schraffiert = verletzt eine Grenze (nicht vergleichbar)", xref="paper", yref="paper", x=0, y=-0.2, showarrow=False, xanchor="left",
                           font=dict(size=11, color=C.MARKER_LINE_COLOR))
    return _lock_axes(fig)
