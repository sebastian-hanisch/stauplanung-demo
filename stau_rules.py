"""Bewertung eines Stauplans und die konstruktiven Regeln (Zielhafen zuerst, Gewicht zuerst, Reparatur, Ankunftsreihenfolge).

Ein Plan ist `stacks`: Liste von Listen (unten -> oben) mit Containern `(zielhafen, gewichtsklasse)`; Lage 0 = unten.

Zielgrößen (alles ganzzahlig):
- **Umstauungen:** Ein Container wird an einem Hafen p umgestaut, wenn unter ihm ein Container mit Zielhafen p steht und sein eigener Zielhafen größer ist. Je Container zählt die
  Zahl der verschiedenen kleineren Zielhäfen unter ihm (beim Löschen von p wird er abgehoben und wieder oben aufgesetzt, bleibt also über den tieferen Containern).
- **Schwerpunkt:** KG = Summe Gewicht x Lage. **Seitenmoment:** Summe (2c - (C-1)) x Stapelgewicht."""

from dataclasses import dataclass


# ---------------------------------------------------------------------------------------------------
# Bewertung
# ---------------------------------------------------------------------------------------------------
def stack_restows(stack):
    """Umstauungen eines Stapels (unten -> oben)."""
    total, seen = 0, set()
    for pod, _ in stack:
        total += len({p for p in seen if p < pod})
        seen.add(pod)
    return total


def restows(stacks):
    return sum(stack_restows(s) for s in stacks)


def kg_sum(stacks):
    return sum(w * t for s in stacks for t, (_, w) in enumerate(s))


def stack_weights(stacks):
    return [sum(w for _, w in s) for s in stacks]


def moment(stacks):
    n = len(stacks)
    return sum((2 * c - (n - 1)) * sum(w for _, w in s) for c, s in enumerate(stacks))


def blockers(stack):
    """Lagen (Indizes) der Container eines Stapels, die umgestaut werden müssen (für das Bay-Bild)."""
    out, seen = set(), set()
    for t, (pod, _) in enumerate(stack):
        if any(p < pod for p in seen):
            out.add(t)
        seen.add(pod)
    return out


@dataclass(frozen=True)
class Limits:
    kg_min: int             # KG der nach Gewicht sortierten Ladeliste (der tiefste erreichbare Schwerpunkt)
    kg_pod: int             # KG der nach Zielhafen sortierten Ladeliste
    kg_limit: int           # eingestellte Schwerpunkt-Grenze L
    tilt_limit: int         # zulässiges Seitenmoment B (Betrag)
    total_weight: int


@dataclass(frozen=True)
class Evaluation:
    restows: int
    kg: int
    moment: int
    violations: tuple       # Namen der verletzten Bedingungen: "Container", "Höhe", "Schwerpunkt", "Seitenneigung"

    @property
    def valid(self):
        return not self.violations


def evaluate(inst, stacks, limits):
    """Umstauungen, Schwerpunkt, Moment und verletzte Bedingungen (Container vollständig, Höhe, Schwerpunkt-Grenze, Seitenneigung)."""
    bad = []
    if sorted(b for s in stacks for b in s) != sorted(inst.boxes) or len(stacks) != inst.n_stacks:
        bad.append("Container")
    if any(len(s) > inst.n_tiers for s in stacks):
        bad.append("Höhe")
    kg, mom = kg_sum(stacks), moment(stacks)
    if kg > limits.kg_limit:
        bad.append("Schwerpunkt")
    if abs(mom) > limits.tilt_limit:
        bad.append("Seitenneigung")
    return Evaluation(restows(stacks), kg, mom, tuple(bad))


# ---------------------------------------------------------------------------------------------------
# Konstruktive Regeln
# ---------------------------------------------------------------------------------------------------
def _arm(c, n_stacks):
    return 2 * c - (n_stacks - 1)


def _layer_positions(n_stacks, n_in_layer):
    """Die Stapelpositionen einer (teilgefüllten) Lage: die mittleren zuerst (Balance), in Stapelreihenfolge."""
    mid = sorted(range(n_stacks), key=lambda c: (abs(_arm(c, n_stacks)), c))
    return sorted(mid[:n_in_layer])


def layered(inst, key):
    """Container nach `key` sortiert, Lage für Lage von unten gefüllt (Lage l = Ränge l*C bis (l+1)*C-1). Innerhalb einer Lage werden die Container (schwere zuerst) jeweils auf die freie
    Position gesetzt, die das Seitenmoment am nächsten an 0 hält."""
    n = inst.n_stacks
    boxes = sorted(inst.boxes, key=key)
    stacks = [[] for _ in range(n)]
    mom = 0
    for start in range(0, len(boxes), n):
        layer = sorted(boxes[start:start + n], key=lambda b: -b[1])
        free = _layer_positions(n, len(layer))
        for box in layer:
            c = min(free, key=lambda c: (abs(mom + _arm(c, n) * box[1]), abs(_arm(c, n)), c))
            free.remove(c)
            mom += _arm(c, n) * box[1]
            stacks[c].append(box)
    return stacks


def pod_sorted(inst):
    """Zielhafen zuerst: fernster Zielhafen unten, innerhalb eines Zielhafens die schweren zuerst: 0 Umstauungen nach Konstruktion."""
    return layered(inst, lambda b: (-b[0], -b[1]))


def weight_sorted(inst):
    """Gewicht zuerst: schwerste unten (tiefster erreichbarer Schwerpunkt), innerhalb gleichen Gewichts der fernste Zielhafen unten."""
    return layered(inst, lambda b: (-b[1], -b[0]))


def arrival(inst):
    """Ankunftsreihenfolge: jeder Container in der Reihenfolge der Ladeliste auf den niedrigsten Stapel (Gleichstand: kleinster Index). Nur als Vergleich, ohne Plan."""
    stacks = [[] for _ in range(inst.n_stacks)]
    for b in inst.boxes:
        c = min(range(inst.n_stacks), key=lambda i: (len(stacks[i]), i))
        stacks[c].append(b)
    return stacks


def _swap_positions(stacks):
    return [(c, t) for c, s in enumerate(stacks) for t in range(len(s))]


def repair(inst, limits, max_iter=200):
    """Sortieren + Reparatur: Start bei der Zielhafen-Sortierung; solange der Schwerpunkt über der Grenze liegt, den Tausch zweier Container wählen, der ihn je zusätzlicher Umstauung
    am günstigsten senkt (und die Seitenneigung einhält); danach Tausche, die Umstauungen senken, ohne die Grenzen zu verletzen. Jeder Kandidat wird inkrementell bewertet
    (Schwerpunkt und Moment aus der Differenz, Umstauungen nur für die betroffenen Stapel)."""
    L, B = limits.kg_limit, limits.tilt_limit
    n = inst.n_stacks
    stacks = pod_sorted(inst)
    arm = [_arm(c, n) for c in range(n)]
    R = [stack_restows(s) for s in stacks]
    mom = moment(stacks)
    kg = kg_sum(stacks)

    def candidate(a, b):
        """Schwerpunkt und Moment nach dem Tausch der Positionen a und b und die neuen Umstauungen der betroffenen Stapel."""
        (c1, t1), (c2, t2) = a, b
        ba, bb = stacks[c1][t1], stacks[c2][t2]
        kg2 = kg + (ba[1] - bb[1]) * (t2 - t1)
        if c1 == c2:
            s = list(stacks[c1])
            s[t1], s[t2] = s[t2], s[t1]
            return kg2, mom, {c1: stack_restows(s)}
        m2 = mom + (arm[c1] - arm[c2]) * (bb[1] - ba[1])
        s1, s2 = list(stacks[c1]), list(stacks[c2])
        s1[t1], s2[t2] = bb, ba
        return kg2, m2, {c1: stack_restows(s1), c2: stack_restows(s2)}

    def apply(a, b, info):
        nonlocal mom, kg
        (c1, t1), (c2, t2) = a, b
        ba, bb = stacks[c1][t1], stacks[c2][t2]
        kg += (ba[1] - bb[1]) * (t2 - t1)
        if c1 != c2:
            mom += (arm[c1] - arm[c2]) * (bb[1] - ba[1])
        stacks[c1][t1], stacks[c2][t2] = bb, ba
        for c, r in info.items():
            R[c] = r

    it = 0
    while kg > L and it < max_iter:
        it += 1
        k0 = kg
        best = None
        pos = _swap_positions(stacks)
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                a, b = pos[i], pos[j]
                wa, wb = stacks[a[0]][a[1]][1], stacks[b[0]][b[1]][1]
                if wa == wb or (wb - wa) * (b[1] - a[1]) <= 0:             # senkt den Schwerpunkt nicht
                    continue
                k2, m2, info = candidate(a, b)
                dk = k0 - k2
                if dk <= 0 or abs(m2) > B:
                    continue
                score = (sum(info.values()) - sum(R[c] for c in info) + 0.5) / dk
                if best is None or score < best[0]:
                    best = (score, a, b, info)
        if best is None:
            break
        apply(best[1], best[2], best[3])
    improved = True
    while improved and it < max_iter * 2:
        improved = False
        it += 1
        r0 = sum(R)
        pos = _swap_positions(stacks)
        best = None
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                a, b = pos[i], pos[j]
                if stacks[a[0]][a[1]] == stacks[b[0]][b[1]]:
                    continue
                if kg + (stacks[a[0]][a[1]][1] - stacks[b[0]][b[1]][1]) * (b[1] - a[1]) > L:
                    continue
                k2, m2, info = candidate(a, b)
                if k2 > L or abs(m2) > B:
                    continue
                r2 = r0 - sum(R[c] for c in info) + sum(info.values())
                if r2 < r0 and (best is None or r2 < best[0]):
                    best = (r2, a, b, info)
        if best:
            apply(best[1], best[2], best[3])
            improved = True
    return stacks
