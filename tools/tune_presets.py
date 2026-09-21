"""Preset-Abstimmung per Sweep: traegt die Geschichte jedes Presets im MITTEL ueber viele Ladelisten, und in der einen Liste, die das Preset zeigt?

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py <modus>
  population   Grundgesamtheit (Seeds 0-19, 2 s Limit): Mittelwert-Kriterien aller Presets
  seeds        je Seed 0..59: welche Presets tragen in dieser Liste, Abstand zum Median der Kennzahlen
  pick         waehlt den Seed, bei dem alle fuenf Presets tragen und die Kennzahlen am naechsten am Median der Listen liegen

Grundsaetze (aus Stapelplanung, Kaiplatz- und Fahrzeug-Demo): den Seed nicht nach dem schoensten Einzelfall waehlen, sondern nahe am MEDIAN (die Verteilungen sind schief);
Kriterien an der Grundgesamtheit messen; alle Presets teilen sich EINE Ladelistennummer, damit die Geschichte 'gleiches Bay, Grenze und Haefen aendern sich' bleibt."""
import math
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, ".")
import stau_constants as C
import stau_evaluation as E
import stau_stories as ST

NAMES = list(C.PRESETS)
SEEDS = range(60)
LIMIT = C.SAMPLE_LIMIT_SECONDS


def _cell(args):
    name, seed = args
    p = C.PRESETS[name]
    return name, seed, E.run_list(p["n_stacks"], p["n_tiers"], p["fill_pct"], p["n_ports"], seed, p["kg_pct"], p["tilt_pct"], LIMIT)


def _table(seeds=SEEDS):
    with ProcessPoolExecutor(max_workers=2) as ex:
        cells = list(ex.map(_cell, [(n, s) for n in NAMES for s in seeds], chunksize=2))
    table = {n: {} for n in NAMES}
    for n, s, r in cells:
        table[n][s] = r
    return table


def cmd_population():
    table = _table(range(C.SAMPLE_LISTS))
    for name in NAMES:
        res = tuple(table[name][s] for s in range(C.SAMPLE_LISTS))
        print(f"\n### {name}")
        for ok, text in ST.criteria(name, res):
            print(("  OK   " if ok else "  FAIL ") + text)
        print("  Kennzahlen:", {k: round(v, 2) for k, v in ST.key_values(name, res).items()}, "| unbewiesen:", E.unproven_count(res))


def _typical(table):
    """Median je Kennzahl (Preset, Verfahren) ueber die Listen."""
    return {(n, k): statistics.median(table[n][s].restows[k] for s in table[n] if table[n][s].valid[k] or True) for n, k in ST.TYPICAL}


def _score(table, med, seed):
    return sum(abs(math.log((table[n][seed].restows[k] or 0) + 0.5) - math.log(med[(n, k)] + 0.5)) for n, k in ST.TYPICAL)


def cmd_seeds():
    table = _table()
    med = _typical(table)
    print("Median je Kennzahl:", {f"{n}/{k}": v for (n, k), v in med.items()})
    for name in NAMES:
        good = [s for s in SEEDS if ST.holds(name, table[name][s])]
        print(f"{name}: traegt in {len(good)} von {len(SEEDS)} Listen")
    allgood = [s for s in SEEDS if all(ST.holds(n, table[n][s]) for n in NAMES)]
    print("\nalle fuenf tragen bei:", sorted(allgood, key=lambda s: _score(table, med, s))[:10])
    for s in sorted(allgood, key=lambda s: _score(table, med, s))[:6]:
        print(f"  seed {s:3d} | Abstand zum Median {_score(table, med, s):.2f} | " + ", ".join(f"{n}: " + "/".join(str(table[n][s].restows[k]) for k in (C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT)) for n in NAMES))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "population"
    {"population": cmd_population, "seeds": cmd_seeds, "pick": cmd_seeds}.get(mode, lambda: sys.exit(__doc__))()
