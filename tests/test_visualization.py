import pytest
from streamlit.testing.v1 import AppTest

import stau_constants as C
import stau_evaluation as E
import stau_exact as X
import stau_rules as R
import stau_scenario as SC
import stau_visualization as V

P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT


@pytest.fixture(scope="module")
def bay():
    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 30, 2)
    return inst, lim, E.run_methods(inst, lim, exact_limit=10)


def traces(fig, name):
    return [t for t in fig.data if t.name == name]


def assert_conventions(fig):
    assert fig.layout.title.text in (None, "")
    for ax in (a for a in fig.layout if a.startswith(("xaxis", "yaxis"))):
        assert fig.layout[ax].fixedrange is True, ax


# ---------------------------------------------------------------------------------------------------
# Bay-Bild
# ---------------------------------------------------------------------------------------------------
def test_bay_conventions_and_axes(bay):
    inst, lim, outs = bay
    fig = V.bay_figure(inst, E.outcome_of(outs, W_).stacks)
    assert_conventions(fig)
    assert list(fig.layout.xaxis.tickvals) == [c + 0.5 for c in range(8)] and list(fig.layout.xaxis.ticktext) == [str(c) for c in range(1, 9)]
    assert list(fig.layout.yaxis.ticktext) == [str(t) for t in range(1, 7)]
    assert fig.layout.xaxis.range[0] < 0 < 8 < fig.layout.xaxis.range[1] and fig.layout.yaxis.range[1] > 6


def test_bay_has_one_shape_per_cell_and_one_per_container(bay):
    inst, lim, outs = bay
    st = E.outcome_of(outs, W_).stacks
    fig = V.bay_figure(inst, st)
    assert len(fig.layout.shapes) == 8 * 6 + 43
    empty = [s for s in fig.layout.shapes if s.fillcolor == C.EMPTY_CELL_COLOR]
    assert len(empty) == 48 and all(s.layer == "below" for s in fig.layout.shapes)
    assert C.EMPTY_CELL_COLOR.startswith("rgba(128,136,149,") and float(C.EMPTY_CELL_COLOR.rstrip(")").split(",")[-1]) < 0.3         # halbtransparent: nichts Weißes im dunklen Schema


def test_bay_marks_exactly_the_restowed_containers_with_a_red_outline(bay):
    inst, lim, outs = bay
    for key, expected in ((W_, 27 - 0), (X_, 0), (R_, None)):
        st = E.outcome_of(outs, key).stacks
        fig = V.bay_figure(inst, st)
        red = [s for s in fig.layout.shapes if s.line.color == C.RESTOW_COLOR]
        assert len(red) == sum(len(R.blockers(s)) for s in st)
        assert all(s.line.width == 3 for s in red) and all(s.line.width == 1 for s in fig.layout.shapes if s.line.color == "rgba(128,136,149,0.5)")
    assert len(V.bay_figure(inst, E.outcome_of(outs, X_).stacks).layout.shapes) == 48 + 43


def test_bay_container_shape_geometry_and_colours(bay):
    inst, lim, outs = bay
    st = E.outcome_of(outs, W_).stacks
    fig = V.bay_figure(inst, st)
    boxes = [s for s in fig.layout.shapes if s.fillcolor != C.EMPTY_CELL_COLOR]
    seen = set()
    for s in boxes:
        c, t = int(s.x0), int(s.y0)
        assert s.x0 == pytest.approx(c + V.CELL_PAD) and s.x1 == pytest.approx(c + 1 - V.CELL_PAD) and s.y1 == pytest.approx(t + 1 - V.CELL_PAD)
        pod, w = st[c][t]
        assert s.fillcolor == C.POD_COLORS[pod - 1] and s.opacity == pytest.approx(0.5 + 0.12 * w)
        seen.add((c, t))
    assert seen == {(c, t) for c, s in enumerate(st) for t in range(len(s))}


def test_bay_weight_digits_sit_in_the_container_centres(bay):
    inst, lim, outs = bay
    st = E.outcome_of(outs, W_).stacks
    digits = traces(V.bay_figure(inst, st), "Gewichtsklassen")[0]
    assert len(digits.x) == 43 and digits.mode == "text"
    for x, y, txt in zip(digits.x, digits.y, digits.text):
        c, t = int(x), int(y)
        assert x == c + 0.5 and y == t + 0.5 and txt == str(st[c][t][1])


def test_bay_hover_points_cover_the_whole_container_rectangle(bay):
    inst, lim, outs = bay
    st = E.outcome_of(outs, W_).stacks
    hover = traces(V.bay_figure(inst, st), "Container")[0]
    assert len(hover.x) == 43 * 9 and hover.marker.opacity == 0
    per_cell = {}
    for x, y, txt in zip(hover.x, hover.y, hover.text):
        per_cell.setdefault((int(x), int(y)), []).append((x, y, txt))
    assert set(per_cell) == {(c, t) for c, s in enumerate(st) for t in range(len(s))}
    for (c, t), pts in per_cell.items():
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        assert len(pts) == 9 and min(xs) < c + 0.4 and max(xs) > c + 0.6 and min(ys) < t + 0.4 and max(ys) > t + 0.6          # Ecken UND Mitte: nicht nur der Mittelpunkt
        assert all(V.CELL_PAD <= x - c <= 1 - V.CELL_PAD and V.CELL_PAD <= y - t <= 1 - V.CELL_PAD for x, y, _ in pts)
        assert f"Zielhafen {st[c][t][0]}" in pts[0][2] and f"Stapel {c + 1}, Lage {t + 1}" in pts[0][2]


def test_bay_hover_text_names_the_ports_at_which_a_container_is_restowed():
    inst = SC.custom_instance([(1, 1), (2, 1), (3, 1)], 1, 3, 3)
    fig = V.bay_figure(inst, [[(1, 1), (2, 1), (3, 1)]])
    texts = sorted(set(traces(fig, "Container")[0].text))
    assert len(texts) == 3
    assert "muss umgestaut werden</b> an Hafen 1, 2" in [t for t in texts if "Zielhafen 3" in t][0]
    two = [t for t in texts if "Zielhafen 2" in t][0]
    assert two.endswith("an Hafen 1") and "1, 2" not in two
    assert "umgestaut" not in [t for t in texts if "Zielhafen 1" in t][0]
    ok = V.bay_figure(inst, [[(3, 1), (2, 1), (1, 1)]])
    assert not any("umgestaut" in t for t in traces(ok, "Container")[0].text)


def test_bay_hover_lists_only_strictly_smaller_ports_once_each():
    inst = SC.custom_instance([(1, 1), (2, 1), (2, 1)], 1, 3, 3)
    texts = sorted(set(traces(V.bay_figure(inst, [[(1, 1), (2, 1), (2, 1)]]), "Container")[0].text))
    two = [t for t in texts if "Lage 3" in t][0]
    assert two.endswith("an Hafen 1")                                        # nicht "1, 2": der gleiche Hafen darunter ist kein Grund


def test_bay_legend_shows_only_ports_that_are_on_board():
    inst = SC.custom_instance([(2, 1), (4, 2)], 2, 2, 5)                     # Häfen 1, 3 und 5 kommen nicht vor
    fig = V.bay_figure(inst, [[(4, 2)], [(2, 1)]])
    assert [t.name for t in fig.data if t.showlegend is not False] == ["Hafen 2", "Hafen 4"]


def test_bay_legend_lists_only_present_ports_and_the_restow_marker(bay):
    inst, lim, outs = bay
    fig = V.bay_figure(inst, E.outcome_of(outs, W_).stacks)
    names = [t.name for t in fig.data if t.showlegend is not False]
    assert names == [f"Hafen {p}" for p in range(1, 6)] + ["Umstauer"] and fig.layout.showlegend is True
    clean = V.bay_figure(inst, E.outcome_of(outs, X_).stacks)
    assert [t.name for t in clean.data if t.showlegend is not False] == [f"Hafen {p}" for p in range(1, 6)]
    quiet = V.bay_figure(inst, E.outcome_of(outs, W_).stacks, legend=False)
    assert quiet.layout.showlegend is False and quiet.layout.margin.t < fig.layout.margin.t and quiet.layout.height < fig.layout.height
    assert not [t for t in quiet.data if t.showlegend is not False]


def test_bay_uses_a_colour_per_port_up_to_seven_and_none_is_near_black_or_white():
    assert len(C.POD_COLORS) == len(C.POD_COLOR_NAMES) == max(C.N_PORTS_RANGE) == 7 and len(set(C.POD_COLORS)) == 7
    for hexcolor in C.POD_COLORS:
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        assert 40 < (r + g + b) / 3 < 215, hexcolor


def test_bay_height_grows_with_the_tiers_and_handles_empty_bay():
    a = V.bay_figure(SC.make_instance(6, 3, 90, 3, 1), [[] for _ in range(6)])
    b = V.bay_figure(SC.make_instance(6, 8, 90, 3, 1), [[] for _ in range(6)])
    assert b.layout.height - a.layout.height == 5 * 40 and len(a.layout.shapes) == 18
    assert len(traces(a, "Container")[0].x) == 0


# ---------------------------------------------------------------------------------------------------
# Frontier
# ---------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def frontier():
    return E.frontier(5, 4, 90, 4, 3, points=(0, 30, 100), n_lists=4, exact_limit=3)


def test_frontier_traces_match_the_curves(frontier):
    fig = V.frontier_figure(frontier, 30)
    assert_conventions(fig)
    for key in (W_, R_, X_):
        tr = traces(fig, C.STRATEGY_LABELS[key])[0]
        vals = [v for v in E.curve(frontier, key) if v is not None]
        idx = [i for i, v in enumerate(E.curve(frontier, key)) if v is not None]
        assert list(tr.y) == pytest.approx(vals) and list(tr.x) == [frontier.points[i] for i in idx]
        assert tr.line.color == C.STRATEGY_COLORS[key]
    pod = traces(fig, C.STRATEGY_LABELS[P_])[0]
    assert list(pod.x) == [100] and list(pod.y) == [0.0] and pod.mode == "markers"                # Zielhafen zuerst nur, wo er zulässig ist


def test_frontier_marks_proven_and_unproven_exact_points():
    def fake(seed, x, proven):
        return E.ListResult(seed, 40, {P_: 0, W_: 9, R_: 1, X_: x}, {P_: False, W_: True, R_: True, X_: True}, proven, "optimal" if proven else "feasible")

    lists = {100: (fake(0, 0, True), fake(1, 0, True)), 30: (fake(0, 0, True), fake(1, 1, False)), 0: (fake(0, 3, False), fake(1, 5, False))}
    fr = E.Frontier((0, 30, 100), lists, 2, 2)
    ex = traces(V.frontier_figure(fr), C.STRATEGY_LABELS[X_])[0]
    assert list(ex.marker.symbol) == ["circle-open", "circle-open", "circle"]
    assert "bewiesen in 0 % der Listen" in ex.text[0] and "bewiesen in 50 %" in ex.text[1] and "bewiesen in 100 %" in ex.text[2]
    assert list(ex.x) == [0, 30, 100] and list(ex.y) == pytest.approx([4, 0.5, 0])
    rep = traces(V.frontier_figure(fr), C.STRATEGY_LABELS[R_])[0]
    assert list(rep.marker.symbol) == ["circle"] * 3 and "zulässig in 100 %" in rep.text[0]


def test_frontier_current_marker_line_is_gray_and_optional(frontier):
    fig = V.frontier_figure(frontier, 30)
    lines = [s for s in fig.layout.shapes if s.type == "line"]
    assert len(lines) == 1 and lines[0].x0 == 30 and lines[0].line.color == C.MARKER_LINE_COLOR
    assert not [s for s in V.frontier_figure(frontier).layout.shapes if s.type == "line"]


def test_frontier_axis_range_and_ticks(frontier):
    fig = V.frontier_figure(frontier)
    assert tuple(fig.layout.xaxis.range) == (-4, 104) and list(fig.layout.xaxis.tickvals) == [0, 30, 100]


def test_frontier_skips_a_method_that_is_never_valid():
    def fake(seed):
        return E.ListResult(seed, 40, {P_: 0, W_: 9, R_: 1, X_: 0}, {P_: False, W_: True, R_: True, X_: True}, True, "optimal")

    fr = E.Frontier((0, 100), {0: (fake(0),), 100: (fake(0),)}, 1, 2)
    assert not traces(V.frontier_figure(fr), C.STRATEGY_LABELS[P_])


# ---------------------------------------------------------------------------------------------------
# Verteilung, Vergleich
# ---------------------------------------------------------------------------------------------------
def test_distribution_and_gain_figures():
    def fake(seed, w, x):
        return E.ListResult(seed, 40, {W_: w, X_: x, R_: x + 1}, {W_: True, X_: True, R_: True}, True, "optimal")

    res = [fake(i, 10, x) for i, x in enumerate([0, 5, 10, 10, 12])]
    dists = [E.distribution(res, X_, W_), E.distribution(res, R_, W_)]
    fig = V.distribution_figure(dists)
    assert_conventions(fig)
    assert len(fig.data) == 3
    for j, d in enumerate(dists):
        assert [t.x[j] for t in fig.data] == pytest.approx([d.better * 100, d.equal * 100, d.worse * 100])
        assert sum(t.x[j] for t in fig.data) == pytest.approx(100)
    assert [t.name for t in fig.data] == ["besser als Gewicht zuerst", "gleich", "schlechter als Gewicht zuerst"]
    g = V.gain_figure(dists)
    assert_conventions(g)
    assert list(g.data[0].y) == pytest.approx([d.median_gain for d in dists]) and list(g.data[1].y) == pytest.approx([d.mean_gain for d in dists])


def test_comparison_figure_hatches_invalid_and_marks_missing(bay):
    inst, lim, outs = bay
    fig = V.comparison_figure(outs)
    assert_conventions(fig)
    bars = [t for t in fig.data]
    assert len(bars) == 8                                                             # 4 Verfahren x 2 Blicke
    restow_bars = bars[:4]
    assert [b.y[0] for b in restow_bars] == [0, 27, 3, 0] and [b.y[0] for b in bars[4:]] == [43, 97, 49, 43]
    assert [b.marker.pattern.shape for b in restow_bars] == ["/", "", "", ""]         # nur Zielhafen zuerst verletzt die Grenze
    assert any("Schraffiert" in a.text for a in fig.layout.annotations) and "Schwerpunkt" in restow_bars[0].hovertemplate
    assert [b.marker.color for b in restow_bars] == [C.STRATEGY_COLORS[k] for k in C.STRATEGY_KEYS]
    ok = E.run_methods(SC.make_instance(6, 5, 90, 5, 4), SC.limits(SC.make_instance(6, 5, 90, 5, 4), 100, 5), exact_limit=3)
    assert not any("Schraffiert" in a.text for a in V.comparison_figure(ok).layout.annotations)


def test_comparison_figure_without_exact_plan_shows_a_dash():
    inst = SC.custom_instance([(1, 1), (1, 2), (2, 1), (3, 3)], 2, 2, 3)
    outs = E.run_methods(inst, SC.limits(inst, 100, 0), exact_limit=3)
    fig = V.comparison_figure(outs)
    assert len(fig.data) == 6 and "–" in fig.layout.xaxis.categoryarray[3] and "–" not in fig.layout.xaxis.categoryarray[0]


# ---------------------------------------------------------------------------------------------------
# Panels über AppTest
# ---------------------------------------------------------------------------------------------------
def _panel_app(mode):
    import dataclasses

    import stau_constants as C
    import stau_evaluation as E
    import stau_exact as X
    import stau_scenario as SC
    import stau_ui_panel as P

    inst = SC.make_instance(8, 6, 90, 5, 31)
    lim = SC.limits(inst, 30, 2)
    outs = E.run_methods(inst, lim, exact_limit=5)
    if mode == "strategies":
        for o in outs:
            P.render_strategy_panel(f"s_{o.key}", o, outs, inst, lim)
        return
    ex = E.outcome_of(outs, C.STRAT_EXACT)
    if mode == "exact_optimal":
        P.render_exact_panel("ex", inst, lim, ex)
    elif mode == "exact_zero_long":
        P.render_exact_panel("ex", inst, lim, ex, long_run=True)
    elif mode == "exact_unproven":
        res = dataclasses.replace(ex.exact, status="feasible", value=3, lower=1, source="Löser")
        P.render_exact_panel("ex", inst, lim, dataclasses.replace(ex, exact=res))
    elif mode == "exact_unproven_rule":
        res = dataclasses.replace(ex.exact, status="feasible", value=3, lower=1, source="Regel")
        P.render_exact_panel("ex", inst, lim, dataclasses.replace(ex, exact=res), long_run=True)
    elif mode == "exact_infeasible":
        none = E.Outcome(C.STRAT_EXACT, ex.label, None, None, None, X.ExactResult("infeasible", None, None, 0, "-", 1.0), E.NO_PLAN_REASONS["infeasible"])
        P.render_exact_panel("ex", inst, lim, none)
    elif mode == "strategies_noplan":
        none = E.Outcome(C.STRAT_EXACT, ex.label, None, None, None, X.ExactResult("infeasible", None, None, 0, "-", 1.0), E.NO_PLAN_REASONS["infeasible"])
        P.render_strategy_panel("s_exact", none, outs[:3] + (none,), inst, lim)
        P.render_strategy_panel("s_weight", outs[1], outs[:3] + (none,), inst, lim)
    elif mode == "exact_unknown":
        none = E.Outcome(C.STRAT_EXACT, ex.label, None, None, None, X.ExactResult("unknown", None, None, 0, "-", 1.0), E.NO_PLAN_REASONS["unknown"])
        P.render_exact_panel("ex", inst, lim, none)


def run_app(mode):
    at = AppTest.from_function(_panel_app, args=(mode,), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def test_strategy_panels_show_four_metrics_and_signed_deltas():
    from streamlit.proto.Metric_pb2 import Metric as MetricProto

    at = run_app("strategies")
    assert [m.label for m in at.metric] == ["Umstauungen", "Kranspiele", "Schwerpunkt", "Seitenneigung"] * 4
    assert [at.metric[4 * i].value for i in range(4)] == ["0 ⚠️", "27", "3", "0"]                # Zielhafen zuerst verletzt die Grenze, das steht im Wert
    assert [at.metric[4 * i].delta for i in range(4)] == ["-27", "", "-24", "-27"]              # Delta = meines minus Gewicht zuerst; die Referenz hat keines
    assert [at.metric[4 * i].proto.color for i in range(4)] == [MetricProto.GRAY, MetricProto.GRAY, MetricProto.GREEN, MetricProto.GREEN]      # weniger Umstauungen ist besser, aber ein unzulässiger Plan (Zielhafen zuerst) gilt nicht als besser: grau
    assert [at.metric[4 * i + 1].value for i in range(4)] == ["43", "97", "49", "43"]
    assert [at.metric[4 * i + 2].value for i in range(3)] == ["208 von 173", "159 von 173", "173 von 173"]
    kg, _, limit = at.metric[14].value.partition(" von ")                                      # der Plan des Lösers ist je Lauf ein anderer (Threads): nur die Grenzen stehen fest
    assert limit == "173" and 159 <= int(kg) <= 173
    assert [at.metric[4 * i + 3].value for i in range(3)] == ["2 von 14", "6 von 14", "8 von 14"] and at.metric[15].value.endswith(" von 14")


def test_invalid_plan_is_flagged_with_the_violation_and_valid_ones_are_not():
    at = run_app("strategies")
    warnings = [w.value for w in at.warning]
    assert len(warnings) == 1 and "Die Schwerpunkt-Grenze ist verletzt" in warnings[0] and "nicht vergleichbar" in warnings[0]
    assert at.metric[2].value == "208 von 173" and at.metric[6].value == "159 von 173"


def test_strategy_panels_use_distinct_chart_keys_and_show_descriptions():
    at = run_app("strategies")
    assert len(at.get("plotly_chart")) == 4
    md = "\n".join(m.value for m in at.markdown)
    for key in C.STRATEGY_KEYS:
        assert C.STRATEGY_DESCRIPTIONS[key] in md
    assert any("Kranzeit 194 min" in c.value for c in at.caption)                         # Gewicht zuerst: 97 Spiele bei 30 je Stunde


def test_exact_panel_optimal_success_and_zero_note():
    at = run_app("exact_optimal")
    assert len(at.success) == 1 and "Bewiesen optimal" in at.success[0].value and "0 Umstauungen sind die untere Schranke" in at.success[0].value
    assert [m.label for m in at.metric] == ["Optimum der Umstauungen"] and at.metric[0].value == "0"
    assert not at.warning and len(at.get("plotly_chart")) == 1


def test_exact_panel_unproven_interval_names_the_limit_and_the_source():
    live = run_app("exact_unproven")
    w = live.warning[0].value
    assert "Nach 4 s" in w and "zwischen **1** und **3**" in w and "Reparatur-Plan" not in w
    assert live.metric[0].label == "Optimum der Umstauungen (beste bekannte)" and live.metric[0].value == "3" and not live.success
    rule = run_app("exact_unproven_rule")
    assert "Nach 30 s" in rule.warning[0].value and "Reparatur-Plan, der Löser fand nichts Besseres" in rule.warning[0].value


def test_exact_panel_without_plan_shows_the_reason_and_no_chart():
    inf = run_app("exact_infeasible")
    assert len(inf.error) == 1 and "keine zulässige Stauung" in inf.error[0].value and not inf.get("plotly_chart") and not inf.metric
    unk = run_app("exact_unknown")
    assert len(unk.warning) == 1 and "Zeitlimit" in unk.warning[0].value and not unk.get("plotly_chart")


def test_exact_panel_caption_reports_limits_moves_and_time():
    at = run_app("exact_optimal")
    assert any("Schwerpunkt" in c.value and "von 173" in c.value and "Kranspiele 43" in c.value and "86 min" in c.value for c in at.caption)


def test_strategy_panel_without_plan_shows_only_the_reason_and_the_others_still_render():
    at = run_app("strategies_noplan")
    assert any("keine zulässige Stauung" in i.value for i in at.info)
    assert len(at.get("plotly_chart")) == 1 and [m.label for m in at.metric] == ["Umstauungen", "Kranspiele", "Schwerpunkt", "Seitenneigung"]
