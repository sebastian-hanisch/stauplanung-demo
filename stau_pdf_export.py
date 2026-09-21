"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute und "×" sind erlaubt, aber "–" (Gedankenstrich), "€", "Σ", "≥", "≤", Emoji usw. lassen fpdf2 abstürzen. Deshalb läuft jeder Text durch
pdf_text(); Verfahren erscheinen mit ihren Kurznamen ohne Emoji."""

import time

import stau_constants as C
import stau_evaluation as E

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "Σ": "Summe", "δ": "Delta", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR",
    "·": "-", "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "±": "+-", "⚠️": "(!)", "⚠": "(!)",
}
P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT


def pdf_text(text):
    """Text für die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def short_name(key):
    return C.STRATEGY_SHORT[key].replace("<br>", " ")


def restow_text(o):
    """Umstauungen eines Verfahrens: Zahl, '<=' bei nicht bewiesenem Optimum, '(!)' bei verletzter Grenze, '-' ohne Plan."""
    if not o.available:
        return "-"
    txt = str(o.restows)
    if o.key == X_ and not o.exact.proven:
        txt = "<= " + txt
    return txt + ("" if o.valid else " (!)")


def verdict_text(sample, label, key, reference):
    """Ein Satz je Vergleich, wie im Kernabschnitt der App (ohne Emoji)."""
    v = E.verdict(sample, key, reference)
    d = E.distribution(sample, key, reference)
    if v.kind == "none":
        return f"{label}: In keiner Ladeliste sind beide Verfahren zulässig, ein Vergleich ist nicht möglich."
    if v.kind == "better":
        amount = f"{abs(v.pct):.0f} % weniger" if v.pct is not None else f"{-v.diff:.1f} weniger"
        return f"{label}: im Mittel {amount} Umstauungen ({-v.diff:.1f} je Ladeliste, Standardfehler {v.se:.2f}); in {d.worse * 100:.0f} % der Ladelisten ist es umgekehrt."
    if v.kind == "worse":
        amount = f"{v.pct:.0f} % mehr" if v.pct is not None else f"{v.diff:.1f} mehr"
        return f"{label}: im Mittel {amount} Umstauungen ({v.diff:.1f} je Ladeliste, Standardfehler {v.se:.2f}); in {d.better * 100:.0f} % der Ladelisten ist es besser."
    return (f"{label}: kein klarer Unterschied, die Differenz ({v.diff:+.1f} je Ladeliste) liegt innerhalb des Rauschens (Standardfehler {v.se:.2f}); "
            f"besser in {d.better * 100:.0f} %, schlechter in {d.worse * 100:.0f} % der Ladelisten.")


def generate_stau_pdf(inst, limits, outcomes, settings, sample=None, frontier=None, compress=True):
    """Ergebnis der aktuellen Einstellung als PDF: Szenario, Zusammenfassung, Verfahrensvergleich, optional Stichprobe/Urteil und Kurve, Hinweise.

    `outcomes`: die vier Outcomes; `settings`: dict mit den Reglerwerten (n_stacks, n_tiers, fill_pct, n_ports, seed, kg_pct, tilt_pct); `sample`: Tupel von ListResult
    oder None; `frontier`: E.Frontier oder None (beides nur, wenn auf Knopfdruck berechnet und zu den Einstellungen passend)."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    by_key = {o.key: o for o in outcomes}
    ref = by_key[W_]
    n = len(inst.boxes)

    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(70, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        """Beginnt einen Abschnitt auf einer neuen Seite, wenn er sonst über den Seitenumbruch liefe (keine halb abgeschnittenen Listen)."""
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    def note(text, size=8):
        pdf.set_font("Helvetica", "I", size)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "B", 16)
    line("Schiffsstauplanung: Stabil stauen, ohne umzustauen?", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    s = settings
    heading("Szenario")
    pairs([
        ("Bay", f"{s['n_stacks']} Stapel x {s['n_tiers']} Lagen, {n} Container ({s['fill_pct']} % gefüllt)"),
        ("Zielhäfen", str(s["n_ports"])),
        ("Seed der Ladeliste", str(s["seed"])),
        ("Schwerpunkt-Grenze", f"{s['kg_pct']} % des Spielraums = {limits.kg_limit}"),
        ("  tiefstmöglicher Schwerpunkt", str(limits.kg_min)),
        ("  Zielhafen-Sortierung", str(limits.kg_pod)),
        ("Seitenneigung", f"{s['tilt_pct']} % des größten Moments = {limits.tilt_limit}"),
    ])
    pdf.ln(3)

    heading("Zusammenfassung")
    rows = []
    for o in outcomes:
        rows.append((short_name(o.key), restow_text(o) + " Umstauungen" + ("" if not o.available or o.key == W_ else f" ({o.restows - ref.restows:+d} gegen Gewicht zuerst)")))
    pairs(rows)
    best = by_key[X_] if by_key[X_].available else by_key[R_]
    if best.valid and ref.valid and best.minutes is not None and ref.minutes - best.minutes > 0:
        note(f"Kranspiele = Container + 2 x Umstauungen: Gewicht zuerst braucht {ref.moves} Spiele ({ref.minutes:.0f} min bei {C.CRANE_MOVES_PER_HOUR} Spielen je Stunde), "
             f"{short_name(best.key)} {best.moves} ({best.minutes:.0f} min): {ref.minutes - best.minutes:.0f} min weniger Kranzeit für diesen Bay.", 9)
    if by_key[X_].exact is not None and by_key[X_].exact.status == "infeasible":
        note("Es gibt keine zulässige Stauung: Schwerpunkt-Grenze und Seitenneigung lassen sich nicht zugleich einhalten (bewiesen).", 9)
    if not by_key[P_].valid:
        note("Zielhafen zuerst hält die Schwerpunkt-Grenze nicht ein; der Plan zählt deshalb nicht als Vergleichswert.", 9)
    pdf.ln(3)

    heading("Verfahrensvergleich")
    table_rows = []
    for r in E.comparison_rows(outcomes):
        o = by_key[r.key]
        if r.available:
            table_rows.append([short_name(r.key), restow_text(o), r.moves, f"{r.minutes:.0f}", f"{r.kg} / {limits.kg_limit}", f"{abs(r.moment)} / {limits.tilt_limit}",
                               "ja" if r.valid else "nein"])
        else:
            table_rows.append([short_name(r.key), "-", "-", "-", "-", "-", "kein Plan"])
    table(["Verfahren", "Umstauungen", "Kranspiele", "Kranzeit (min)", "Schwerpunkt", "Seitenmoment", "zulässig"], [38, 28, 24, 28, 28, 28, 16], table_rows)
    ex = by_key[X_]
    interval = E.exact_interval(ex)
    if interval is not None and not interval[2]:
        note(f"Exakt ist nicht bewiesen: das Optimum liegt zwischen {interval[0]} und {interval[1]} Umstauungen (nach {C.EXACT_LIVE_LIMIT_SECONDS} s Zeitlimit).")
    else:
        note("Umstauungen: Container, die beim Löschen abgehoben und zurückgesetzt werden müssen (je Hafen, an dem sie im Weg stehen). Ein Optimum von 0 ist per Definition bewiesen.")
    pdf.ln(3)

    if sample is not None:
        keep_together(95)
        heading("Stichprobe und Urteil")
        table(["Verfahren", "Umstauungen im Mittel", "zulässig in (%)"], [50, 60, 40],
              [[short_name(k), "-" if E.mean_restows(sample, k) is None else f"{E.mean_restows(sample, k):.1f}", f"{E.valid_share(sample, k) * 100:.0f}"] for k in C.STRATEGY_KEYS])
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        for label, key, reference in (("Exakt gegen Gewicht zuerst", X_, W_), ("Exakt gegen Sortieren + Reparatur", X_, R_), ("Sortieren + Reparatur gegen Gewicht zuerst", R_, W_)):
            pdf.multi_cell(0, 5, pdf_text("- " + verdict_text(sample, label, key, reference)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        note(f"Basis: {len(sample)} Ladelisten (Seeds 0-{len(sample) - 1}, nicht der eingestellte Seed) mit den eingestellten Werten. Klar heißt: Unterschied größer als zwei Standardfehler der gepaarten "
             f"Differenz, nur über Listen, in denen beide Verfahren zulässig sind. In {E.unproven_count(sample)} von {len(sample)} Listen ist Exakt nicht bewiesen (Obergrenze).")
        pdf.ln(3)

    if frontier is not None:
        keep_together(80)
        heading("Umstauungen über der Schwerpunkt-Grenze")
        pts = frontier.points
        cw = [44] + [max(14, int(146 / len(pts)))] * len(pts)
        rows = []
        for key in (W_, R_, X_):
            vals = E.curve(frontier, key)
            rows.append([short_name(key)] + ["-" if v is None else f"{v:.1f}" for v in vals])
        table(["Grenze in %"] + [str(p) for p in pts], cw, rows)
        kante = E.kante(frontier)
        note(f"Basis: {len(pts)} Grenzwerte x {frontier.n_lists} Ladelisten (Seeds 0-{frontier.n_lists - 1}), Seitenneigung {frontier.tilt_pct} %. "
             + (f"Ab einer Grenze von {kante} % abwärts kostet auch das Optimum im Mittel mehr als eine halbe Umstauung (die Kante)." if kante is not None
                else "Im untersuchten Bereich kostet auch das Optimum im Mittel höchstens eine halbe Umstauung."))
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Ein Bay, ein Ladehafen: Container haben einen Zielhafen (1 bis 7) und eine von vier Gewichtsklassen. Stapel stehen ohne Lücken; keine Reefer, 20/40-Fuß-Unterschiede, Gefahrgut, Stapelgewichtsgrenzen.",
        "Stabilität ist als Summe Gewicht x Lage (Schwerpunkt-Grenze) und Seitenmoment modelliert, keine Klassifikationsrechnung eines Schiffs.",
        f"Kranspiele = Container + 2 x Umstauungen bei {C.CRANE_MOVES_PER_HOUR} Spielen je Stunde: eine Annahme, keine Messung.",
        "Die Reparatur-Heuristik ist eine eigene Konstruktion; der Exakt-Löser (CP-SAT) beweist das Optimum, wo das Zeitlimit reicht, sonst steht ein Intervall.",
        "Alle Zahlen sind Größenordnungen aus einer Simulation mit zufälligen Ladelisten, keine Messung an echten Bay-Plänen.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
