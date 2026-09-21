"""Exakter Löser: kleinste Zahl von Umstauungen bei eingehaltener Schwerpunkt-Grenze und Seitenneigung (CP-SAT).

Modell: Zellen (Stapel c, Lage t) x Container-Typen k (Zielhafen x Gewichtsklasse); `x[c,t,k]` = 1, wenn ein Container vom Typ k dort steht. Schwerkraft (keine Lücke unten), Anzahl je
Typ, Schwerpunkt- und Seitenneigungs-Grenze als lineare Bedingungen. Umstauungen: `b[c,t,p]` = 1, wenn unter Lage t ein Container mit Zielhafen p steht, `r[c,t,p]` >= b + [Container in
(c,t) hat Zielhafen > p] - 1, Zielfunktion Summe r (entspricht `stau_rules.restows`, im Test gegengeprüft).

Ergebnisse tragen ihre Beweislage: `optimal` (bewiesen), `feasible` (Plan da, Optimum nicht bewiesen: Intervall [untere Schranke, Wert]), `infeasible` (bewiesen: keine zulässige Stauung),
`unknown` (im Zeitlimit weder Plan noch Beweis). Nie wird ein unbewiesener Wert als Optimum ausgegeben. Ein Wert von 0 ist per Definition bewiesen (untere Schranke 0)."""

import math
import os
import time
from dataclasses import dataclass

import stau_constants as C
import stau_rules as R

NUM_SEARCH_WORKERS = min(8, os.cpu_count() or 1)


@dataclass(frozen=True)
class ExactResult:
    status: str             # "optimal" | "feasible" | "infeasible" | "unknown"
    stacks: object          # Plan (Liste von Listen) oder None
    value: object           # Umstauungen des Plans oder None
    lower: int              # bewiesene untere Schranke der Umstauungen (0, wenn nichts bekannt)
    source: str             # "Löser", "Regel" (Reparatur mit 0 Umstauungen bzw. Rückfall) oder "-" ohne Plan
    wall_ms: float

    @property
    def proven(self):
        """Ist die Aussage bewiesen (Optimum oder Unzulässigkeit)?"""
        return self.status in ("optimal", "infeasible")


def _solve_model(inst, limits, time_limit, hint, workers):
    """CP-SAT: (Status-Name, Plan oder None, Zielwert oder None, untere Schranke)."""
    from ortools.sat.python import cp_model

    n_c, n_t, n_p = inst.n_stacks, inst.n_tiers, inst.n_ports
    types = sorted(set(inst.boxes))
    count = {ty: inst.boxes.count(ty) for ty in types}
    m = cp_model.CpModel()
    x = {(c, t, k): m.NewBoolVar(f"x{c}_{t}_{k}") for c in range(n_c) for t in range(n_t) for k in range(len(types))}
    occ = {}
    for c in range(n_c):
        for t in range(n_t):
            occ[c, t] = sum(x[c, t, k] for k in range(len(types)))
            m.Add(occ[c, t] <= 1)
        for t in range(1, n_t):
            m.Add(occ[c, t] <= occ[c, t - 1])                             # Schwerkraft: keine Lücke unten
    for k, ty in enumerate(types):
        m.Add(sum(x[c, t, k] for c in range(n_c) for t in range(n_t)) == count[ty])
    weights = [sum(types[k][1] * x[c, t, k] for t in range(n_t) for k in range(len(types))) for c in range(n_c)]
    mom = sum((2 * c - (n_c - 1)) * weights[c] for c in range(n_c))
    m.Add(mom <= limits.tilt_limit)
    m.Add(mom >= -limits.tilt_limit)
    m.Add(sum(types[k][1] * t * x[c, t, k] for c in range(n_c) for t in range(n_t) for k in range(len(types))) <= limits.kg_limit)

    pres = {(c, t, p): sum(x[c, t, k] for k in range(len(types)) if types[k][0] == p) for c in range(n_c) for t in range(n_t) for p in range(1, n_p + 1)}
    cost = []
    for c in range(n_c):
        for p in range(1, n_p):
            below = []
            for t in range(n_t):
                b = m.NewBoolVar(f"b{c}_{t}_{p}")
                below.append(b)
                if t == 0:
                    m.Add(b == 0)
                else:
                    m.Add(b >= below[t - 1])
                    m.Add(b >= pres[c, t - 1, p])
                r = m.NewBoolVar(f"r{c}_{t}_{p}")
                m.Add(r >= b + sum(pres[c, t, q] for q in range(p + 1, n_p + 1)) - 1)
                cost.append(r)
    m.Minimize(sum(cost))
    if hint is not None:
        for c, s in enumerate(hint):
            for t in range(n_t):
                for k, ty in enumerate(types):
                    m.AddHint(x[c, t, k], int(t < len(s) and s[t] == ty))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers
    status = solver.Solve(m)
    if status == cp_model.INFEASIBLE:
        return "infeasible", None, None, 0
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "unknown", None, None, max(0, math.ceil(solver.BestObjectiveBound() - 1e-6))
    stacks = [[ty for t in range(n_t) for k, ty in enumerate(types) if solver.Value(x[c, t, k])] for c in range(n_c)]
    value = int(round(solver.ObjectiveValue()))
    lower = value if status == cp_model.OPTIMAL else max(0, math.ceil(solver.BestObjectiveBound() - 1e-6))
    return ("optimal" if status == cp_model.OPTIMAL else "feasible"), stacks, value, lower


def solve_exact(inst, limits, time_limit=C.EXACT_LIVE_LIMIT_SECONDS, use_hint=True, workers=NUM_SEARCH_WORKERS):
    """Kleinste Zahl von Umstauungen mit Zeitlimit. Startlösung und Rückfall ist die Reparatur (wenn sie zulässig ist). Hat die Reparatur 0 Umstauungen, ist das bewiesen optimal
    (untere Schranke 0) und der Löser läuft nicht."""
    t0 = time.perf_counter()
    rule = R.repair(inst, limits) if use_hint else None
    rule_ev = R.evaluate(inst, rule, limits) if rule is not None else None
    rule_ok = rule_ev is not None and rule_ev.valid

    def elapsed():
        return (time.perf_counter() - t0) * 1000

    if rule_ok and rule_ev.restows == 0:
        return ExactResult("optimal", rule, 0, 0, "Regel", elapsed())
    status, stacks, value, lower = _solve_model(inst, limits, time_limit, rule if rule_ok else None, workers)
    if status == "infeasible":
        return ExactResult("infeasible", None, None, 0, "-", elapsed())
    if stacks is not None and (not rule_ok or value <= rule_ev.restows):
        return ExactResult(status, stacks, value, lower, "Löser", elapsed())
    if rule_ok:                                                          # der Löser fand nichts oder nichts Besseres: die Regel bleibt, ausdrücklich nicht bewiesen
        return ExactResult("feasible", rule, rule_ev.restows, lower, "Regel", elapsed())
    return ExactResult("unknown", None, None, lower, "-", elapsed())
