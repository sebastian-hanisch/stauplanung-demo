"""Testhilfen: unabhängige Vergleichsimplementierungen (Löschsimulation, naive Reparatur, Brute Force) und Instanz-Generatoren."""
import itertools
import random

import stau_scenario as SC
import stau_rules as R


def random_instance(seed, max_stacks=12, max_tiers=8):
    """Zufällige Ladeliste innerhalb der Reglergrenzen der App (4 bis 12 Stapel, 3 bis 8 Lagen, höchstens 96 Zellen)."""
    rng = random.Random(seed)
    n_stacks, n_tiers = rng.randint(4, max_stacks), rng.randint(3, max_tiers)
    while n_stacks * n_tiers > 96:
        n_tiers -= 1
    return SC.make_instance(n_stacks, n_tiers, rng.choice([50, 65, 80, 90, 100]), rng.randint(2, 7), rng.randint(0, 9999))


def small_instance(seed):
    """Kleine Ladeliste (schnell genug für die naive Reparatur als Referenz)."""
    return random_instance(seed, max_stacks=7, max_tiers=5)


def random_stacks(seed):
    """Zufällige (oft unsinnige) Stapel zum Vergleich der Bewertungsformel mit der Simulation."""
    rng = random.Random(seed)
    return [[(rng.randint(1, 6), rng.randint(1, 4)) for _ in range(rng.randint(0, 7))] for _ in range(rng.randint(1, 6))]


def discharge_restows(stacks):
    """Umstauungen durch Simulation des Löschens Hafen für Hafen (unabhängig von der Formel): An Hafen p wird in jedem Stapel alles über dem untersten Container mit Zielhafen p
    abgehoben (Umstauer, wenn deren Zielhafen größer ist), die Container mit Zielhafen p verlassen das Schiff, die Umstauer kommen in derselben Reihenfolge zurück."""
    stacks = [list(s) for s in stacks]
    ports = sorted({p for s in stacks for p, _ in s})
    moved = 0
    for p in ports:
        for s in stacks:
            lowest = next((i for i, (pod, _) in enumerate(s) if pod == p), None)
            if lowest is None:
                continue
            above = s[lowest + 1:]
            moved += sum(1 for pod, _ in above if pod > p)
            s[:] = [b for b in s[:lowest] if b[0] != p] + [b for b in above if b[0] != p]
    return moved


def naive_repair(inst, limits, max_iter=200):
    """Die ursprüngliche, langsame Fassung der Reparatur (jeder Kandidat wird vollständig neu bewertet): Referenz für die inkrementelle Fassung."""
    L, B = limits.kg_limit, limits.tilt_limit
    stacks = R.pod_sorted(inst)

    def swapped(s, a, b):
        t = [list(x) for x in s]
        t[a[0]][a[1]], t[b[0]][b[1]] = t[b[0]][b[1]], t[a[0]][a[1]]
        return t

    it = 0
    while R.kg_sum(stacks) > L and it < max_iter:
        it += 1
        r0, k0 = R.restows(stacks), R.kg_sum(stacks)
        best = None
        pos = [(c, t) for c, s in enumerate(stacks) for t in range(len(s))]
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                a, b = pos[i], pos[j]
                if stacks[a[0]][a[1]][1] == stacks[b[0]][b[1]][1]:
                    continue
                t = swapped(stacks, a, b)
                dk = k0 - R.kg_sum(t)
                if dk <= 0 or abs(R.moment(t)) > B:
                    continue
                score = (R.restows(t) - r0 + 0.5) / dk
                if best is None or score < best[0]:
                    best = (score, t)
        if best is None:
            break
        stacks = best[1]
    improved = True
    while improved and it < max_iter * 2:
        improved = False
        it += 1
        r0 = R.restows(stacks)
        pos = [(c, t) for c, s in enumerate(stacks) for t in range(len(s))]
        best = None
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                a, b = pos[i], pos[j]
                if stacks[a[0]][a[1]] == stacks[b[0]][b[1]]:
                    continue
                t = swapped(stacks, a, b)
                if R.kg_sum(t) > L or abs(R.moment(t)) > B:
                    continue
                r = R.restows(t)
                if r < r0 and (best is None or r < best[0]):
                    best = (r, t)
        if best:
            stacks, improved = best[1], True
    return stacks


def all_arrangements(inst):
    """Alle Anordnungen der Ladeliste in den Bay (Brute Force, nur für winzige Listen): Stapelinhalte jeweils in allen Reihenfolgen."""
    boxes = inst.boxes
    for assign in itertools.product(range(inst.n_stacks), repeat=len(boxes)):
        groups = [[] for _ in range(inst.n_stacks)]
        for b, c in zip(boxes, assign):
            groups[c].append(b)
        if any(len(g) > inst.n_tiers for g in groups):
            continue
        perms = [set(itertools.permutations(g)) for g in groups]
        for combo in itertools.product(*perms):
            yield [list(p) for p in combo]


def tiny_instances(n=25):
    out = []
    for i in range(n):
        rng = random.Random(i)
        n_stacks, n_tiers = 3, 3
        boxes = [(rng.randint(1, 3), rng.randint(1, 3)) for _ in range(rng.randint(5, 7))]
        out.append(SC.custom_instance(boxes, n_stacks, n_tiers, 3))
    return out
