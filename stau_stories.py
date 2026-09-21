"""Abnahmekriterien der Presets (Plan, Abschnitt 7): Welche Geschichte erzählt jedes Beispielszenario, und woran erkennt man, dass sie trägt?

Einzige Quelle für `tools/tune_presets.py` (Abstimmung) und `tests/test_preset_stories.py` (Abnahme). Jedes Kriterium ist eine Aussage über ein Tupel von `ListResult`s
(stau_evaluation): über viele Ladelisten die Aussage im MITTEL (`criteria`), über die EINE Liste des Presets die Aussage in dieser Liste (`holds`). So wird dieselbe Geschichte an
der Grundgesamtheit UND an der gewählten Liste geprüft: das Preset soll typisch sein, nicht der schönste Einzelfall. Umstauungen sind ganze Zahlen; ein Verfahren ohne zulässigen Plan
zählt in keinem Mittelwert (`E.values`)."""

import stau_constants as C
import stau_evaluation as E

P_, W_, R_, X_ = C.STRAT_POD, C.STRAT_WEIGHT, C.STRAT_REPAIR, C.STRAT_EXACT

# Kennzahlen, an denen 'typisch' gemessen wird: (Preset, Verfahren)
TYPICAL = (("Locker", W_), ("Üblich", W_), ("Üblich", R_), ("Knapp", R_), ("Am Limit", X_), ("Am Limit", R_), ("Viele Häfen", W_), ("Viele Häfen", R_))


def _mean(results, key):
    m = E.mean_restows(results, key)
    return float("nan") if m is None else m


def criteria(name, results):
    """Mittelwert-Kriterien über viele Ladelisten. Rückgabe: Liste (erfüllt, Text)."""
    v = E.valid_share
    if name == "Locker":
        return [(v(results, P_) == 1.0, f"Zielhafen zuerst zulässig in {v(results, P_) * 100:.0f} % der Listen"),
                (all(x == 0 for x in E.values(results, P_)), f"Zielhafen zuerst ohne Umstauung: {_mean(results, P_):.2f}"),
                (_mean(results, W_) >= 15, f"Gewicht zuerst >= 15 Umstauungen: {_mean(results, W_):.1f}")]
    if name == "Üblich":
        return [(v(results, P_) == 0.0, f"Zielhafen zuerst unzulässig in {(1 - v(results, P_)) * 100:.0f} % der Listen"),
                (_mean(results, X_) == 0, f"Exakt 0 in allen Listen (eine 0 ist immer bewiesen): {_mean(results, X_):.2f}"),
                (_mean(results, R_) <= 1.0, f"Reparatur im Mittel <= 1: {_mean(results, R_):.2f}"),
                (_mean(results, W_) >= 15, f"Gewicht zuerst >= 15 Umstauungen: {_mean(results, W_):.1f}")]
    if name == "Knapp":
        return [(_mean(results, X_) == 0, f"Exakt 0 in allen Listen (eine 0 ist immer bewiesen): {_mean(results, X_):.2f}"),
                (_mean(results, R_) >= 1.0, f"Reparatur im Mittel >= 1: {_mean(results, R_):.2f}")]
    if name == "Am Limit":
        return [(_mean(results, X_) >= 0.5, f"Exakt im Mittel >= 0,5: {_mean(results, X_):.2f}"),
                (_mean(results, R_) - _mean(results, X_) >= 2.0, f"Reparatur >= 2 über Exakt: {_mean(results, R_):.2f} gegen {_mean(results, X_):.2f}")]
    if name == "Viele Häfen":
        better = sum(1 for r in results if r.valid[R_] and r.valid[X_] and r.restows[X_] < r.restows[R_]) / len(results)
        return [(_mean(results, W_) >= 25, f"Gewicht zuerst >= 25 Umstauungen: {_mean(results, W_):.1f}"),
                (_mean(results, R_) >= 1.5, f"Reparatur im Mittel >= 1,5: {_mean(results, R_):.2f}"),
                (better >= 0.7, f"Exakt besser als Reparatur in >= 70 % der Listen: {better * 100:.0f} %")]
    raise KeyError(name)


def holds(name, r):
    """Gilt die Geschichte in der EINEN Ladeliste (`ListResult`), die das Preset zeigt?"""
    rs, ok = r.restows, r.valid
    if name == "Locker":
        return ok[P_] and rs[P_] == 0 and ok[W_] and rs[W_] >= 15
    if name == "Üblich":
        return not ok[P_] and ok[X_] and rs[X_] == 0 and ok[R_] and rs[R_] <= 2 and ok[W_] and rs[W_] >= 15
    if name == "Knapp":
        return not ok[P_] and ok[X_] and rs[X_] == 0 and ok[R_] and rs[R_] >= 1
    if name == "Am Limit":
        return ok[X_] and rs[X_] >= 1 and ok[R_] and rs[R_] - rs[X_] >= 2
    if name == "Viele Häfen":
        return ok[W_] and rs[W_] >= 25 and ok[R_] and ok[X_] and rs[R_] >= 1 and rs[X_] < rs[R_]
    raise KeyError(name)


def key_values(name, results):
    """Die Kennzahlen dieses Presets aus TYPICAL als {Verfahren: Mittel}."""
    return {k: _mean(results, k) for n, k in TYPICAL if n == name}


