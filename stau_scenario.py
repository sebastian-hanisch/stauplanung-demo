"""Ladeliste aus den Reglerwerten, Spielraum des Schwerpunkts und die Grenzen L und B.

Zwei getrennte Fragen: Welche Container sind an Bord (`make_instance`, eigener Zufallsstrom, bestimmt nur die Ladeliste) und welche Grenzen gelten (`limits`, reine Rechnung)."""

import random
from dataclasses import dataclass

import stau_constants as C
from stau_rules import Limits, kg_sum, pod_sorted, weight_sorted


@dataclass(frozen=True)
class Instance:
    n_stacks: int
    n_tiers: int
    n_ports: int
    boxes: tuple            # Container in Ankunftsreihenfolge: (Zielhafen 1..n_ports, Gewichtsklasse 1..WEIGHT_CLASSES)

    @property
    def cells(self):
        return self.n_stacks * self.n_tiers


def n_boxes(n_stacks, n_tiers, fill_pct):
    """Zahl der Container: Füllgrad in ganzen Prozent der Zellen, kaufmännisch gerundet (mindestens 1)."""
    return max(1, (fill_pct * n_stacks * n_tiers * 2 + 100) // 200)


def make_instance(n_stacks, n_tiers, fill_pct, n_ports, seed):
    """Ladeliste mit eigenem Zufallsstrom (`seed` bestimmt nur die Container): Zielhafen und Gewichtsklasse gleichverteilt und unabhängig."""
    if n_stacks < 1 or n_tiers < 1 or n_ports < 1:
        raise ValueError("Stapel, Lagen und Häfen mindestens 1")
    if not 0 < fill_pct <= 100:
        raise ValueError("Füllgrad zwischen 1 und 100 %")
    rng = random.Random(seed)
    boxes = []
    for _ in range(n_boxes(n_stacks, n_tiers, fill_pct)):
        pod = rng.randint(1, n_ports)
        boxes.append((pod, rng.randint(1, C.WEIGHT_CLASSES)))
    return Instance(n_stacks, n_tiers, n_ports, tuple(boxes))


def custom_instance(boxes, n_stacks, n_tiers, n_ports):
    """Eigene Ladeliste (Tests und Handfälle); prüft, dass sie in den Bay passt und die Werte gültig sind."""
    boxes = tuple((int(p), int(w)) for p, w in boxes)
    if not boxes:
        raise ValueError("mindestens ein Container")
    if len(boxes) > n_stacks * n_tiers:
        raise ValueError("mehr Container als Zellen")
    if any(not 1 <= p <= n_ports for p, _ in boxes):
        raise ValueError("Zielhafen außerhalb von 1 bis n_ports")
    if any(not 1 <= w <= C.WEIGHT_CLASSES for _, w in boxes):
        raise ValueError("Gewichtsklasse außerhalb von 1 bis WEIGHT_CLASSES")
    return Instance(n_stacks, n_tiers, n_ports, boxes)


def limits(inst, kg_pct, tilt_pct):
    """Grenzen aus den Reglerwerten. Der Schwerpunkt-Grenze L liegt bei `kg_pct` % des Spielraums zwischen dem tiefstmöglichen Schwerpunkt (nach Gewicht sortiert) und dem der Zielhafen-Sortierung
    (ganzzahlig abgerundet): 100 % = die Zielhafen-Sortierung ist gerade noch erlaubt, 0 % = nur der tiefste Schwerpunkt. Das zulässige Seitenmoment B ist `tilt_pct` % des größten
    möglichen Moments (Gesamtgewicht x (Stapel - 1))."""
    if not 0 <= kg_pct <= 100:
        raise ValueError("Schwerpunkt-Grenze zwischen 0 und 100 %")
    if tilt_pct < 0:
        raise ValueError("Seitenneigung nicht negativ")
    kmin, kpod = kg_sum(weight_sorted(inst)), kg_sum(pod_sorted(inst))
    total = sum(w for _, w in inst.boxes)
    return Limits(kmin, kpod, kmin + (kg_pct * (kpod - kmin)) // 100, (tilt_pct * total * (inst.n_stacks - 1)) // 100, total)
