import re

import pytest

import stau_constants as C
import stau_evaluation as E
import stau_scenario as SC
from stau_evaluation import ListResult
from stau_pdf_export import generate_stau_pdf, pdf_text, restow_text, short_name, verdict_text

P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT
_cache = {}


def _settings(name="Knapp", **override):
    p = dict(C.PRESETS[name])
    p.update(override)
    return p


def _pdf(name="Knapp", compress=False, sample=None, frontier=None, **override):
    s = _settings(name, **override)
    key = (name, tuple(sorted(override.items())))
    if key not in _cache:
        inst = SC.make_instance(s["n_stacks"], s["n_tiers"], s["fill_pct"], s["n_ports"], s["seed"])
        lim = SC.limits(inst, s["kg_pct"], s["tilt_pct"])
        _cache[key] = (inst, lim, E.run_methods(inst, lim, 2))
    inst, lim, outs = _cache[key]
    return generate_stau_pdf(inst, lim, outs, s, sample=sample, frontier=frontier, compress=compress), inst, lim, outs, s


def _texts(data):
    """Alle Textstücke des (unkomprimierten) PDFs als Liste, Latin-1 gelesen, PDF-Escapes aufgelöst."""
    raw = re.findall(rb"\((.*?)\)\s*Tj", data)
    return [t.decode("latin-1").replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\") for t in raw]


def _after(text, label):
    return text[text.index(label) + 1]


def lr(seed, **rs):
    r = dict({P_: 0, W_: 26, R_: 2, X_: 0}, **rs)
    return ListResult(seed, 48, r, {P_: False, W_: True, R_: True, X_: True}, True, "optimal")


# ---------- Sonderzeichen: mit den GENAUEN Zeichen testen (fpdf2 stürzt bei "–" und "€" ab) ----------
EXPECTED = {"–": "-", "—": "-", "−": "-", "€": "EUR", "Σ": "Summe", "δ": "Delta", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "„": '"', "“": '"', "’": "'", "·": "-", "±": "+-",
            "⚠️": "(!)", "⚠": "(!)"}


@pytest.mark.parametrize("char,replacement", list(EXPECTED.items()))
def test_pdf_text_replaces_every_known_troublemaker_with_a_readable_equivalent(char, replacement):
    out = pdf_text(f"a{char}b")
    out.encode("latin-1")
    assert out == f"a{replacement}b"


def test_pdf_text_keeps_umlauts_and_times_sign_and_replaces_unknown():
    assert pdf_text("Füllgrad äöüß ÄÖÜ × 3") == "Füllgrad äöüß ÄÖÜ × 3"
    assert pdf_text("日本語").encode("latin-1") == b"???"
    assert "?" in pdf_text("🧮 Exakt")


def test_short_names_have_no_line_breaks_and_no_emoji():
    for key in C.STRATEGY_KEYS:
        name = short_name(key)
        assert "<br>" not in name and pdf_text(name) == name
    assert short_name(R_) == "Sortieren + Reparatur" and short_name(P_) == "Zielhafen zuerst"


def test_every_text_the_app_can_put_into_the_pdf_survives_latin_1():
    for text in (C.STRATEGY_LABELS.values()):
        pdf_text(text).encode("latin-1")


# ---------- Inhalt ----------
def test_pdf_is_a_valid_document_with_all_sections_without_sample():
    data, *_ = _pdf()
    assert data.startswith(b"%PDF") and data.endswith(b"%%EOF\n") and len(data) > 2000
    text = _texts(data)
    for needle in ["Schiffsstauplanung: Stabil stauen, ohne umzustauen?", "Szenario", "Zusammenfassung", "Verfahrensvergleich", "Hinweise zum Modell"]:
        assert needle in text, needle
    assert "Stichprobe und Urteil" not in text and "Umstauungen über der Schwerpunkt-Grenze" not in text


def test_pdf_scenario_block_pairs_every_label_with_its_own_value():
    data, inst, lim, outs, s = _pdf()
    text = _texts(data)
    assert _after(text, "Bay") == "8 Stapel x 6 Lagen, 43 Container (90 % gefüllt)" and _after(text, "Zielhäfen") == "5"
    assert _after(text, "Seed der Ladeliste") == str(s["seed"])
    assert _after(text, "Schwerpunkt-Grenze") == f"30 % des Spielraums = {lim.kg_limit}"
    assert _after(text, "  tiefstmöglicher Schwerpunkt") == str(lim.kg_min) and _after(text, "  Zielhafen-Sortierung") == str(lim.kg_pod)
    assert _after(text, "Seitenneigung") == f"2 % des größten Moments = {lim.tilt_limit}"


def test_pdf_scenario_follows_the_settings():
    data, inst, lim, outs, s = _pdf("Viele Häfen", n_stacks=6, n_tiers=5, fill_pct=70, seed=9)
    text = _texts(data)
    assert _after(text, "Bay") == f"6 Stapel x 5 Lagen, {len(inst.boxes)} Container (70 % gefüllt)" and _after(text, "Zielhäfen") == "7" and _after(text, "Seed der Ladeliste") == "9"
    assert _after(text, "Schwerpunkt-Grenze").startswith("30 % ")


def test_pdf_summary_quotes_each_method_with_its_signed_difference():
    data, inst, lim, outs, s = _pdf()
    text = _texts(data)
    by = {o.key: o for o in outs}
    ref = by[W_].restows
    assert _after(text, short_name(W_)).startswith(f"{ref} Umstauungen") and "gegen Gewicht zuerst" not in _after(text, short_name(W_))
    for k in (R_, X_):
        assert _after(text, short_name(k)) == f"{restow_text(by[k])} Umstauungen ({by[k].restows - ref:+d} gegen Gewicht zuerst)"
    assert _after(text, short_name(P_)).endswith("(!) Umstauungen (" + f"{by[P_].restows - ref:+d} gegen Gewicht zuerst)") or "(!)" in _after(text, short_name(P_))


def test_pdf_states_the_crane_time_saved_and_why_pod_first_does_not_count():
    text = " ".join(_texts(_pdf()[0]))
    assert "Kranspiele = Container + 2 x Umstauungen" in text and "min weniger Kranzeit für diesen Bay" in text and "Zielhafen zuerst hält die Schwerpunkt-Grenze nicht ein" in text
    text2 = " ".join(_texts(_pdf("Locker")[0]))
    assert "Zielhafen zuerst hält die Schwerpunkt-Grenze nicht ein" not in text2


def test_pdf_comparison_table_rows_are_complete_and_in_column_order():
    data, inst, lim, outs, s = _pdf()
    text = _texts(data)
    start = text.index("zulässig") + 1
    for i, o in enumerate(outs):
        row = text[start + 7 * i: start + 7 * i + 7]
        assert row == [short_name(o.key), restow_text(o), str(o.moves), f"{o.minutes:.0f}", f"{o.evaluation.kg} / {lim.kg_limit}", f"{abs(o.evaluation.moment)} / {lim.tilt_limit}",
                       "ja" if o.valid else "nein"], (o.key, row)


def test_pdf_marks_a_method_without_plan_with_a_plain_dash():
    inst = SC.make_instance(6, 4, 90, 5, 3)
    lim = SC.limits(inst, 30, 1)
    outs = E.run_methods(inst, SC.limits(inst, 100, 0), 1)
    if outs[3].available:                                                             # sicherstellen, dass dieser Fall wirklich "kein Plan" ist
        pytest.skip("keine Unzulässigkeit in dieser Ladeliste")
    data = generate_stau_pdf(inst, lim, outs, _settings(n_stacks=6, n_tiers=4, seed=3, tilt_pct=0), compress=False)
    text = _texts(data)
    start = text.index("zulässig") + 1
    assert text[start + 21: start + 28] == [short_name(X_), "-", "-", "-", "-", "-", "kein Plan"]
    assert "–" not in " ".join(text) and any("keine zulässige Stauung" in t for t in text)


def test_pdf_shows_an_unproven_exact_result_as_an_interval():
    from stau_exact import ExactResult
    from stau_evaluation import Outcome
    import stau_rules as RU
    data0, inst, lim, outs, s = _pdf()
    plan = RU.repair(inst, lim)
    ev = RU.evaluate(inst, plan, lim)
    fake = Outcome(X_, C.STRATEGY_LABELS[X_], plan, ev, E.crane_moves(len(inst.boxes), ev.restows), ExactResult("feasible", plan, ev.restows, max(0, ev.restows - 1), "Regel", 1.0))
    text = _texts(generate_stau_pdf(inst, lim, outs[:3] + (fake,), s, compress=False))
    assert _after(text, short_name(X_)).startswith(f"<= {ev.restows} Umstauungen")
    assert any(f"zwischen {max(0, ev.restows - 1)} und {ev.restows} Umstauungen" in t for t in text)


# ---------- Stichprobe, Urteil, Kurve ----------
def test_pdf_sample_section_lists_means_shares_and_the_three_verdicts():
    sample = tuple(lr(i, weight=26 + i % 3, repair=2 + i % 2, exact=0) for i in range(10))
    text = _texts(_pdf(sample=sample)[0])
    assert "Stichprobe und Urteil" in text
    start = text.index("zulässig in (%)") + 1
    assert text[start: start + 3] == [short_name(P_), "-", "0"]
    assert text[start + 3: start + 6] == [short_name(W_), f"{E.mean_restows(sample, W_):.1f}", "100"]
    joined = " ".join(text)
    for label in ("Exakt gegen Gewicht zuerst", "Exakt gegen Sortieren + Reparatur", "Sortieren + Reparatur gegen Gewicht zuerst"):
        assert label in joined
    assert "Basis: 10 Ladelisten (Seeds 0-9, nicht der eingestellte Seed)" in joined and "In 0 von 10 Listen ist Exakt nicht bewiesen" in joined


def test_pdf_frontier_section_has_one_row_per_method_and_one_column_per_point():
    pts = (0, 30, 100)
    fr = E.Frontier(pts, {p: tuple(lr(i, exact=(2 if p == 0 else 0), repair=3) for i in range(4)) for p in pts}, 4, 2)
    text = _texts(_pdf(frontier=fr)[0])
    assert "Umstauungen über der Schwerpunkt-Grenze" in text
    start = text.index("Grenze in %") + 1
    assert text[start: start + 3] == ["0", "30", "100"]
    assert text[start + 3: start + 7] == [short_name(W_), "26.0", "26.0", "26.0"]
    assert text[start + 7: start + 11] == [short_name(R_), "3.0", "3.0", "3.0"]
    assert text[start + 11: start + 15] == [short_name(X_), "2.0", "0.0", "0.0"]
    joined = " ".join(text)
    assert "Basis: 3 Grenzwerte x 4 Ladelisten (Seeds 0-3), Seitenneigung 2 %" in joined and "Ab einer Grenze von 0 % abwärts" in joined


def test_pdf_frontier_without_a_kante_says_so():
    fr = E.Frontier((0, 100), {p: tuple(lr(i, exact=0) for i in range(3)) for p in (0, 100)}, 3, 2)
    assert "höchstens eine halbe Umstauung" in " ".join(_texts(_pdf(frontier=fr)[0]))


def test_pdf_frontier_marks_a_method_without_valid_lists_with_a_dash():
    fr = E.Frontier((0, 100), {p: tuple(ListResult(i, 48, {P_: None, W_: 26, R_: 2, X_: None}, {P_: False, W_: True, R_: True, X_: False}, True, "infeasible") for i in range(3)) for p in (0, 100)}, 3, 2)
    text = _texts(_pdf(frontier=fr)[0])
    start = text.index("Grenze in %") + 1
    assert text[start + 8: start + 11] == [short_name(X_), "-", "-"]


@pytest.mark.parametrize("kind,expected", [("better", "weniger"), ("worse", "mehr"), ("unclear", "kein klarer Unterschied"), ("none", "In keiner Ladeliste")])
def test_verdict_text_covers_all_states(kind, expected):
    if kind == "better":
        sample = tuple(lr(i, exact=0, weight=20 + i) for i in range(10))
        text = verdict_text(sample, "L", X_, W_)
    elif kind == "worse":
        sample = tuple(lr(i, exact=20 + i, weight=1) for i in range(10))
        text = verdict_text(sample, "L", X_, W_)
    elif kind == "unclear":
        sample = tuple(lr(i, exact=(i % 2) * 2, weight=1) for i in range(10))
        text = verdict_text(sample, "L", X_, W_)
    else:
        sample = tuple(ListResult(i, 48, {P_: 0, W_: 5, R_: 1, X_: None}, {P_: False, W_: True, R_: True, X_: False}, True, "infeasible") for i in range(4))
        text = verdict_text(sample, "L", X_, W_)
    assert expected in text and text.startswith("L:")
    text.encode("latin-1")


def test_verdict_text_percent_and_absolute_variants():
    better = tuple(lr(i, exact=0, weight=20 + i) for i in range(10))
    assert "% weniger Umstauungen" in verdict_text(better, "L", X_, W_)
    zero_ref = tuple(lr(i, exact=1 + i, weight=0) for i in range(10))
    assert "mehr Umstauungen" in verdict_text(zero_ref, "L", X_, W_) and "%" not in verdict_text(zero_ref, "L", X_, W_).split("(")[0]


# ---------- Ränder ----------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_pdf_is_generated_for_every_preset_compressed_and_uncompressed(name):
    for compress in (True, False):
        data = _pdf(name, compress=compress)[0]
        assert data.startswith(b"%PDF") and len(data) > 1500


def test_pdf_at_the_limits_stays_valid():
    tiny = _pdf(n_stacks=4, n_tiers=3, fill_pct=50, n_ports=2, tilt_pct=5)[0]
    big = _pdf(n_stacks=12, n_tiers=8, fill_pct=100, n_ports=7, kg_pct=100)[0]
    assert tiny.startswith(b"%PDF") and big.startswith(b"%PDF")


def _pages(data):
    """Textstücke je Seite (unkomprimiertes PDF: ein Inhaltsstrom je Seite)."""
    streams = re.findall(rb"stream\r?\n(.*?)endstream", data, re.S)
    return [[t.decode("latin-1") for t in re.findall(rb"\((.*?)\)\s*Tj", s)] for s in streams]


def test_pdf_sections_are_not_split_across_pages():
    sample = tuple(lr(i) for i in range(20))
    fr = E.Frontier(C.FRONTIER_POINTS, {p: tuple(lr(i) for i in range(8)) for p in C.FRONTIER_POINTS}, 8, 2)
    pages = _pages(_pdf(sample=sample, frontier=fr)[0])
    assert len(pages) <= 3
    for head, last in (("Stichprobe und Urteil", "In 0 von 20 Listen ist Exakt nicht bewiesen"), ("Umstauungen über der Schwerpunkt-Grenze", "halbe Umstauung"), ("Hinweise zum Modell", "echten Bay-Plänen.")):
        page = next(p for p in pages if head in p)
        assert any(last in t for t in page) or last in " ".join(page), head
        assert page.index(head) < len(page) - 3, head


# ---------- Feinheiten (aus dem Fehler-Einbau-Test) ----------
def _fake_outcome(key, restows, valid=True, proven=True, plan=True):
    import stau_rules as RU
    from stau_exact import ExactResult
    from stau_evaluation import Outcome
    ev = RU.Evaluation(restows, 100, 0, () if valid else ("Schwerpunkt",)) if plan else None
    ex = ExactResult("optimal" if proven else "feasible", [] if plan else None, restows, restows if proven else 0, "Löser", 1.0) if key == X_ else None
    return Outcome(key, C.STRATEGY_LABELS[key], [] if plan else None, ev, E.crane_moves(43, restows) if plan else None, ex, "" if plan else "kein Plan")


def test_restow_text_covers_plan_proof_and_validity():
    assert restow_text(_fake_outcome(X_, 0, plan=False)) == "-"
    assert restow_text(_fake_outcome(X_, 3)) == "3"                                   # bewiesen: keine Schranke
    assert restow_text(_fake_outcome(X_, 3, proven=False)) == "<= 3"
    assert restow_text(_fake_outcome(R_, 3, proven=False)) == "3"                     # nur Exakt trägt die Schranke
    assert restow_text(_fake_outcome(P_, 0, valid=False)) == "0 (!)"


def _bays(*keys_and_values):
    inst, lim, outs, s = _pdf()[1:]
    return inst, lim, s


def _outs(pod=0, weight=26, repair=2, exact=0, **flags):
    return (_fake_outcome(P_, pod, valid=flags.get("pod_valid", False)), _fake_outcome(W_, weight), _fake_outcome(R_, repair, valid=flags.get("repair_valid", True)),
            _fake_outcome(X_, exact, plan=flags.get("exact_plan", True), valid=flags.get("exact_valid", True)))


def _text_for(outs, **kw):
    inst, lim, s = _bays()
    return " ".join(_texts(generate_stau_pdf(inst, lim, outs, s, compress=False, **kw)))


def test_the_crane_time_note_names_the_best_valid_method_and_needs_a_real_saving():
    assert "Exakt 43" in _text_for(_outs(exact=0, repair=2))                          # Exakt ist das beste Verfahren, wenn es einen Plan hat
    assert "Sortieren + Reparatur 47" in _text_for(_outs(exact_plan=False, repair=2))
    assert "min weniger Kranzeit" not in _text_for(_outs(exact=26))                   # gleiche Kranzeit wie die Referenz: kein Gewinn zu melden
    assert "min weniger Kranzeit" not in _text_for(_outs(exact_valid=False))          # ein Plan, der eine Grenze verletzt, spart nichts
    assert "min weniger Kranzeit" not in _text_for(_outs(exact_plan=False, repair=2, repair_valid=False))


def test_verdict_sentences_pair_each_label_with_its_own_comparison():
    sample = tuple(lr(i, weight=20, repair=4 + i % 2, exact=i % 3) for i in range(12))
    text = _text_for(_outs(), sample=sample)
    for label, key, ref in (("Exakt gegen Gewicht zuerst", X_, W_), ("Exakt gegen Sortieren + Reparatur", X_, R_), ("Sortieren + Reparatur gegen Gewicht zuerst", R_, W_)):
        assert verdict_text(sample, label, key, ref) in text, label


def test_verdict_reverse_shares_name_the_right_side():
    mixed_better = tuple(lr(i, weight=20, exact=(0 if i < 8 else 30)) for i in range(10))
    t = verdict_text(mixed_better, "L", X_, W_)
    assert "weniger" in t and "in 20 % der Ladelisten ist es umgekehrt" in t
    mixed_worse = tuple(lr(i, weight=20, exact=(40 if i < 8 else 0)) for i in range(10))
    t = verdict_text(mixed_worse, "L", X_, W_)
    assert "mehr Umstauungen" in t and "in 20 % der Ladelisten ist es besser" in t


def test_a_small_sample_still_gets_its_section():
    assert "Stichprobe und Urteil" in _text_for(_outs(), sample=tuple(lr(i) for i in range(3)))


def test_frontier_note_quotes_the_tilt_of_the_frontier_not_of_the_scenario():
    fr = E.Frontier((0, 100), {p: tuple(lr(i) for i in range(3)) for p in (0, 100)}, 3, 4)
    assert "Seitenneigung 4 %" in _text_for(_outs(), frontier=fr)                     # das Szenario steht auf 2 %
