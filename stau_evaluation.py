"""Auswertung: ein Bay mit allen Verfahren, Stichprobe über viele Ladelisten, Frontier-Kurve über die Schwerpunkt-Grenze, gepaarte Differenz, Verteilung und Urteil.

Reine Rechnung ohne Streamlit. Kosten sind Umstauungen; ein Plan zählt nur, wenn er beide Grenzen einhält (`valid`): Ein Verfahren, das eine Grenze verletzt, hat kein vergleichbares
Ergebnis. Kranspiele = Container + 2 x Umstauungen (abheben und zurücksetzen). Alle Vergleiche sind gepaart (dieselben Ladelisten)."""

import math
import statistics
from dataclasses import dataclass

import stau_constants as C
import stau_exact as X
import stau_rules as R
import stau_scenario as SC


# ---------------------------------------------------------------------------------------------------
# Ein Bay, alle Verfahren
# ---------------------------------------------------------------------------------------------------
def crane_moves(n_boxes, restows):
    """Kranspiele für die Bay: jeder Container einmal, jede Umstauung zweimal (abheben, zurücksetzen)."""
    return n_boxes + 2 * restows


def crane_minutes(moves):
    """Kranzeit in Minuten bei CRANE_MOVES_PER_HOUR Spielen je Stunde (Annahme)."""
    return moves * 60 / C.CRANE_MOVES_PER_HOUR


@dataclass(frozen=True)
class Outcome:
    key: str
    label: str
    stacks: object          # Plan oder None (Exakt ohne Plan)
    evaluation: object      # R.Evaluation oder None
    moves: object           # Kranspiele oder None
    exact: object = None    # nur beim Exakt-Verfahren: das ExactResult
    reason: str = ""        # Begründung, wenn es keinen Plan gibt

    @property
    def available(self):
        return self.stacks is not None

    @property
    def restows(self):
        return self.evaluation.restows if self.evaluation else None

    @property
    def valid(self):
        return bool(self.evaluation and self.evaluation.valid)

    @property
    def violations(self):
        return self.evaluation.violations if self.evaluation else ()

    @property
    def minutes(self):
        return crane_minutes(self.moves) if self.moves is not None else None


NO_PLAN_REASONS = {
    "infeasible": "Es gibt keine zulässige Stauung: Schwerpunkt-Grenze und Seitenneigung lassen sich nicht zugleich einhalten (bewiesen). Die Neigung erhöhen oder die Grenze lockern.",
    "unknown": "Im Zeitlimit wurde weder ein zulässiger Plan gefunden noch die Unzulässigkeit bewiesen.",
}


def run_methods(inst, limits, exact_limit=C.EXACT_LIVE_LIMIT_SECONDS):
    """Alle vier Verfahren auf derselben Ladeliste mit denselben Grenzen. Exakt läuft mit `exact_limit` Sekunden und liefert bei Nichtbeweis ein Intervall (`outcome.exact`)."""
    n = len(inst.boxes)
    plans = {C.STRAT_POD: R.pod_sorted(inst), C.STRAT_WEIGHT: R.weight_sorted(inst), C.STRAT_REPAIR: R.repair(inst, limits)}
    out = []
    for key in (C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR):
        ev = R.evaluate(inst, plans[key], limits)
        out.append(Outcome(key, C.STRATEGY_LABELS[key], plans[key], ev, crane_moves(n, ev.restows)))
    out.append(exact_outcome(inst, limits, exact_limit))
    return tuple(out)


def exact_outcome(inst, limits, exact_limit=C.EXACT_LIVE_LIMIT_SECONDS):
    """Nur das Exakt-Verfahren (für das lange Nachrechnen im Exakt-Tab): dieselbe Outcome-Form wie in `run_methods`."""
    res = X.solve_exact(inst, limits, exact_limit)
    label = C.STRATEGY_LABELS[C.STRAT_EXACT]
    if res.stacks is None:
        return Outcome(C.STRAT_EXACT, label, None, None, None, res, NO_PLAN_REASONS[res.status])
    ev = R.evaluate(inst, res.stacks, limits)
    return Outcome(C.STRAT_EXACT, label, res.stacks, ev, crane_moves(len(inst.boxes), ev.restows), res)


def outcome_of(outcomes, key):
    return next(o for o in outcomes if o.key == key)


@dataclass(frozen=True)
class Row:
    key: str
    label: str
    available: bool
    restows: object
    moves: object
    minutes: object
    kg: object
    moment: object
    valid: bool
    violations: tuple
    delta_vs_baseline: object       # meine minus Referenz (Umstauungen); None ohne Plan
    reason: str


def comparison_rows(outcomes, baseline=C.BASELINE):
    ref = outcome_of(outcomes, baseline).restows
    rows = []
    for o in outcomes:
        ev = o.evaluation
        rows.append(Row(o.key, o.label, o.available, o.restows, o.moves, o.minutes, ev.kg if ev else None, ev.moment if ev else None, o.valid, o.violations,
                        None if o.restows is None or ref is None else o.restows - ref, o.reason))
    return tuple(rows)


def exact_interval(outcome):
    """(untere Schranke, Wert, bewiesen) des Exakt-Ergebnisses; None ohne Plan."""
    res = outcome.exact
    if res is None or res.value is None:
        return None
    return res.lower, res.value, res.proven


# ---------------------------------------------------------------------------------------------------
# Stichprobe: viele Ladelisten
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ListResult:
    seed: int
    n_boxes: int
    restows: dict           # Verfahren -> Umstauungen (None ohne Plan)
    valid: dict             # Verfahren -> hält beide Grenzen ein
    proven: bool            # Exakt: bewiesen (Optimum oder Unzulässigkeit)
    exact_status: str


def run_list(n_stacks, n_tiers, fill_pct, n_ports, seed, kg_pct, tilt_pct, exact_limit):
    inst = SC.make_instance(n_stacks, n_tiers, fill_pct, n_ports, seed)
    outs = run_methods(inst, SC.limits(inst, kg_pct, tilt_pct), exact_limit)
    exact = outcome_of(outs, C.STRAT_EXACT)
    return ListResult(seed, len(inst.boxes), {o.key: o.restows for o in outs}, {o.key: o.valid for o in outs}, exact.exact.proven, exact.exact.status)


def sample(n_stacks, n_tiers, fill_pct, n_ports, kg_pct, tilt_pct, n_lists=C.SAMPLE_LISTS, exact_limit=C.SAMPLE_LIMIT_SECONDS, progress=None):
    """Ladelisten mit den Seeds 0..n_lists-1 (unabhängig vom eingestellten Seed) mit den eingestellten Bay- und Grenzwerten, alle Verfahren je Liste."""
    out = []
    for i, seed in enumerate(range(n_lists)):
        out.append(run_list(n_stacks, n_tiers, fill_pct, n_ports, seed, kg_pct, tilt_pct, exact_limit))
        if progress:
            progress((i + 1) / n_lists)
    return tuple(out)


def frontier_plan(n_stacks, n_tiers):
    """(Punkte in %, Anzahl Listen): ab FRONTIER_LARGE_CELLS Zellen weniger von beidem (Laufzeit)."""
    if n_stacks * n_tiers > C.FRONTIER_LARGE_CELLS:
        return C.FRONTIER_POINTS_LARGE, C.FRONTIER_LISTS_LARGE
    return C.FRONTIER_POINTS, C.FRONTIER_LISTS


@dataclass(frozen=True)
class Frontier:
    points: tuple           # Schwerpunkt-Grenze in %
    lists: dict             # Punkt -> Tupel von ListResult (gleiche Ladelisten an jedem Punkt)
    n_lists: int
    tilt_pct: int


def frontier(n_stacks, n_tiers, fill_pct, n_ports, tilt_pct, exact_limit=C.SAMPLE_LIMIT_SECONDS, points=None, n_lists=None, progress=None):
    """Umstauungen der Verfahren über der Schwerpunkt-Grenze (die Frontier): dieselben Ladelisten (Seeds 0..) an jedem Punkt."""
    default_points, default_lists = frontier_plan(n_stacks, n_tiers)
    points = tuple(points or default_points)
    n_lists = n_lists or default_lists
    lists, done, total = {}, 0, len(points) * n_lists
    for pct in points:
        rows = []
        for seed in range(n_lists):
            rows.append(run_list(n_stacks, n_tiers, fill_pct, n_ports, seed, pct, tilt_pct, exact_limit))
            done += 1
            if progress:
                progress(done / total)
        lists[pct] = tuple(rows)
    return Frontier(points, lists, n_lists, tilt_pct)


# ---------------------------------------------------------------------------------------------------
# Statistik über Ladelisten (gepaart)
# ---------------------------------------------------------------------------------------------------
def _se(xs):
    return statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0


def values(results, key):
    """Umstauungen des Verfahrens über die Listen, in denen es einen zulässigen Plan hat."""
    return [r.restows[key] for r in results if r.valid[key]]


def valid_share(results, key):
    return sum(1 for r in results if r.valid[key]) / len(results)


def mean_restows(results, key):
    v = values(results, key)
    return statistics.fmean(v) if v else None


def median_restows(results, key):
    v = values(results, key)
    return statistics.median(v) if v else None


def unproven_count(results):
    """Zahl der Listen, in denen das Exakt-Ergebnis nicht bewiesen ist (der Wert ist dort eine Obergrenze des Optimums)."""
    return sum(1 for r in results if not r.proven)


def paired(results, key, reference):
    """Gepaarte Differenz key - reference über die Listen, in denen BEIDE zulässig sind: Liste der Differenzen (Umstauungen, negativ = key besser)."""
    return [r.restows[key] - r.restows[reference] for r in results if r.valid[key] and r.valid[reference]]


@dataclass(frozen=True)
class Distribution:
    key: str
    n: int                  # Listen, in denen beide zulässig sind
    better: float           # Anteile (0..1) gegen die Referenz
    equal: float
    worse: float
    mean_gain: float        # Referenz minus Verfahren (positiv = besser), Umstauungen je Liste
    median_gain: float


def distribution(results, key, reference=C.BASELINE):
    d = paired(results, key, reference)
    n = len(d)
    if n == 0:
        return Distribution(key, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
    better, worse = sum(1 for x in d if x < 0), sum(1 for x in d if x > 0)
    return Distribution(key, n, better / n, (n - better - worse) / n, worse / n, -statistics.fmean(d), -statistics.median(d))


@dataclass(frozen=True)
class Verdict:
    kind: str               # "better" | "worse" | "unclear" | "none" (keine gemeinsam zulässige Liste)
    diff: float             # Verfahren minus Referenz, Umstauungen je Liste (negativ = besser)
    se: float
    pct: object             # Unterschied in % der Referenz (negativ = besser); None, wenn die Referenz im Mittel 0 hat
    n: int
    worse_share: float


def verdict(results, key, reference=C.BASELINE):
    """Bewertung gegen die Referenz. 'Klar' heißt: Unterschied > VERDICT_Z Standardfehler der gepaarten Differenz; sonst 'unclear'; 'none', wenn keine Liste beide zulässig hat."""
    d = paired(results, key, reference)
    if not d:
        return Verdict("none", 0.0, 0.0, None, 0, 0.0)
    diff, se = statistics.fmean(d), _se(d)
    ref_mean = statistics.fmean(r.restows[reference] for r in results if r.valid[key] and r.valid[reference])
    if se == 0:
        kind = "unclear" if diff == 0 else ("better" if diff < 0 else "worse")
    else:
        kind = "unclear" if abs(diff) <= C.VERDICT_Z * se else ("better" if diff < 0 else "worse")
    return Verdict(kind, diff, se, 100.0 * diff / ref_mean if ref_mean else None, len(d), sum(1 for x in d if x > 0) / len(d))


# ---------------------------------------------------------------------------------------------------
# Frontier: Kurven
# ---------------------------------------------------------------------------------------------------
def curve(fr, key):
    """Mittlere Umstauungen des Verfahrens je Punkt der Frontier (über die Listen mit zulässigem Plan); None, wo keine Liste zulässig ist."""
    return tuple(mean_restows(fr.lists[p], key) for p in fr.points)


def curve_valid_share(fr, key):
    return tuple(valid_share(fr.lists[p], key) for p in fr.points)


def curve_proven(fr):
    """Anteil der Listen je Punkt, in denen das Exakt-Ergebnis bewiesen ist."""
    return tuple(1 - unproven_count(fr.lists[p]) / len(fr.lists[p]) for p in fr.points)


def kante(fr, threshold=0.5):
    """Erste (lockerste) Grenze in %, ab der das Optimum im Mittel über `threshold` Umstauungen liegt, wenn man von 100 % nach 0 % geht; None, wenn es nie darüber liegt."""
    hit = None
    for p in sorted(fr.points, reverse=True):
        m = mean_restows(fr.lists[p], C.STRAT_EXACT)
        if m is not None and m > threshold:
            hit = p
            break
    return hit
