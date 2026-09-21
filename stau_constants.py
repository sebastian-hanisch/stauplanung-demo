"""Regler-Grenzen, Vorgaben und feste Parameter der Stauplanung-Demo.

Ein Bay (Stapel x Lagen), ein Ladehafen, Container mit Zielhafen und Gewichtsklasse, alles ganzzahlig."""

# --- Regler: Grenzen und Vorgaben ---
N_STACKS_RANGE, N_STACKS_DEFAULT = (4, 12), 8
N_TIERS_RANGE, N_TIERS_DEFAULT = (3, 8), 6
MAX_CELLS = 96                          # Stapel x Lagen höchstens so viele (Reichweite des Exakt-Lösers), 12 x 8 = 96 ist die größte Kombination
FILL_PCT_RANGE, FILL_PCT_STEP, FILL_PCT_DEFAULT = (50, 100), 5, 90
N_PORTS_RANGE, N_PORTS_DEFAULT = (2, 7), 5
SEED_RANGE, SEED_DEFAULT = (0, 9999), 31
KG_PCT_RANGE, KG_PCT_STEP, KG_PCT_DEFAULT = (0, 100), 5, 30      # Schwerpunkt-Grenze in % des Spielraums (100 = Zielhafen-Sortierung erlaubt, 0 = tiefster Schwerpunkt)
TILT_PCT_RANGE, TILT_PCT_DEFAULT = (1, 5), 2                     # zulässige Seitenneigung in % des größten möglichen Moments (mindestens 1: bei 0 gibt es praktisch keinen Plan)

# --- feste Parameter ---
WEIGHT_CLASSES = 4                      # Gewichtsklassen 1 (leicht) bis 4 (schwer)
CRANE_MOVES_PER_HOUR = 30               # Annahme: Kranspiele je Stunde (nur für die Umrechnung von Umstauungen in Kranzeit)
EXACT_LIVE_LIMIT_SECONDS = 4            # Exakt in der Hauptansicht
EXACT_LONG_LIMIT_SECONDS = 30           # Exakt-Tab auf Knopfdruck
SAMPLE_LIMIT_SECONDS = 2                # je Ladeliste in Stichprobe und Kurve

# --- Verfahren (Schlüssel -> Beschriftung, in Anzeigereihenfolge); "Gewicht zuerst" ist die Referenz aller Deltas ---
STRAT_POD, STRAT_WEIGHT, STRAT_REPAIR, STRAT_EXACT = "pod", "weight", "repair", "exact"
STRATEGY_LABELS = {
    STRAT_POD: "🏁 Zielhafen zuerst",
    STRAT_WEIGHT: "⚖️ Gewicht zuerst",
    STRAT_REPAIR: "🔧 Sortieren + Reparatur",
    STRAT_EXACT: "🧮 Exakt",
}
STRATEGY_SHORT = {STRAT_POD: "Zielhafen<br>zuerst", STRAT_WEIGHT: "Gewicht<br>zuerst", STRAT_REPAIR: "Sortieren +<br>Reparatur", STRAT_EXACT: "Exakt"}
STRATEGY_KEYS = tuple(STRATEGY_LABELS)
BASELINE = STRAT_WEIGHT

# --- Presets: eine gemeinsame Ladeliste (Seed), Grenze und Häfen wechseln (Werte vorläufig, AP 6 stimmt sie gegen die Abnahmekriterien ab) ---
_BASE = dict(n_stacks=N_STACKS_DEFAULT, n_tiers=N_TIERS_DEFAULT, fill_pct=FILL_PCT_DEFAULT, seed=SEED_DEFAULT, tilt_pct=TILT_PCT_DEFAULT)
PRESETS = {
    "Locker": dict(_BASE, n_ports=5, kg_pct=100),
    "Üblich": dict(_BASE, n_ports=5, kg_pct=60),
    "Knapp": dict(_BASE, n_ports=5, kg_pct=30),
    "Am Limit": dict(_BASE, n_ports=5, kg_pct=0),
    "Viele Häfen": dict(_BASE, n_ports=7, kg_pct=30),
}

# --- Stichprobe und Frontier-Kurve (Ladelisten mit den Seeds 0.. , nicht der eingestellte Seed) ---
SAMPLE_LISTS = 20                       # Ladelisten der Stichprobe beim eingestellten Wert
FRONTIER_LISTS, FRONTIER_LISTS_LARGE = 8, 6
FRONTIER_POINTS = (0, 10, 20, 30, 50, 75, 100)          # Schwerpunkt-Grenze in %
FRONTIER_POINTS_LARGE = (0, 10, 30, 60, 100)
FRONTIER_LARGE_CELLS = 60               # ab so vielen Zellen weniger Listen und Punkte (Laufzeit: 6 x 5 in 14 s, 8 x 6 in 29 s, 12 x 8 in 85 s bei 7 x 8)
VERDICT_Z = 2.0                         # "klar" heißt gepaarte Differenz > VERDICT_Z Standardfehler

# --- Darstellung ---
POD_COLORS = ("#2a6fb0", "#2e7d4f", "#c77700", "#7a3fb0", "#b0356a", "#1a8a8a", "#8a94a3")     # Zielhafen 1..7
POD_COLOR_NAMES = ("blau", "grün", "orange", "violett", "rosa", "türkis", "grau")
RESTOW_COLOR = "#d62728"                # roter Rand: dieser Container muss umgestaut werden
EMPTY_CELL_COLOR = "rgba(128,136,149,0.14)"      # leere Zelle: halbtransparentes Mittelgrau (hell und dunkel lesbar)
MARKER_LINE_COLOR = "#808895"           # mittleres Grau: auf hellem und dunklem Grund sichtbar
STRATEGY_COLORS = {STRAT_POD: "#2a6fb0", STRAT_WEIGHT: "#8a94a3", STRAT_REPAIR: "#c77700", STRAT_EXACT: "#2e7d4f"}
OUTCOME_COLORS = {"better": "#2e7d4f", "equal": "#b8bfc9", "worse": "#c0392b"}
CHART_HEIGHT = 420
STRATEGY_DESCRIPTIONS = {
    STRAT_POD: "**Zielhafen zuerst.** Container nach Zielhafen sortiert, der fernste unten, Lage für Lage; innerhalb eines Hafens die schweren zuerst. **0 Umstauungen** nach Konstruktion, "
               "aber der Schwerpunkt liegt so hoch wie möglich: Sobald die Schwerpunkt-Grenze unter 100 % liegt, ist der Plan unzulässig.",
    STRAT_WEIGHT: "**Gewicht zuerst.** Die schwersten Container nach unten (tiefster erreichbarer Schwerpunkt), Lage für Lage, innerhalb gleichen Gewichts der fernste Zielhafen unten. "
                  "Stabil, aber ohne Rücksicht auf die Häfen: viele Umstauungen. Die Referenz aller Vergleiche.",
    STRAT_REPAIR: "**Sortieren + Reparatur.** Start bei der Zielhafen-Sortierung; solange der Schwerpunkt über der Grenze liegt, wird der Tausch zweier Container gewählt, der ihn je zusätzlicher "
                  "Umstauung am günstigsten senkt; danach Tausche, die Umstauungen senken. Kann die Grenze in seltenen Fällen verfehlen (dann steht „Grenze verletzt“).",
    STRAT_EXACT: "**Exakt (CP-SAT).** Die kleinste Zahl von Umstauungen, die beide Grenzen einhält, mit Beweis oder Intervall [untere Schranke, beste Lösung], wenn das Zeitlimit nicht reicht. "
                 "Ein Optimum von 0 ist per Definition bewiesen.",
}

# --- Ansicht ---
RIGHT_VIEW_KEYS = (STRAT_POD, STRAT_REPAIR, STRAT_EXACT)     # im Bay-Blick steht links immer Gewicht zuerst
VIEW_DEFAULT = STRAT_EXACT
