# Schiffsstauplanung: Stabil stauen, ohne umzustauen? – Streamlit-Demo

Interaktive Fall-Demo zur **Stauplanung eines Bays**: Ein Schiff wird in einem Hafen beladen und läuft mehrere Häfen an. Was im nächsten Hafen von Bord muss, darf nicht unter dem liegen,
was weiter fährt, sonst muss **umgestaut** werden (abheben, löschen, zurücksetzen). Zugleich muss der Bay **stabil** stehen: Schweres nach unten, die Seiten im Gleichgewicht. Beide
Wünsche ziehen in entgegengesetzte Richtungen. Die Demo beantwortet: **Was kostet die Stabilität wirklich?**

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning", Welle 3 der Hafen-Linie (Schiff → Kran; nach der Fahrzeug-Demo
`fahrzeugflotte-demo`, der Kaiplatz-Demo `robuste-kaiplatz-demo` und der Stapelplanung `stapelplanung-demo`).

## Warum dieses Problem

Die beiden einfachen Regeln scheitern auf entgegengesetzte Weise: **Nach Zielhafen sortieren** kostet null Umstauungen, aber der Schwerpunkt liegt so hoch wie möglich, der Plan ist unter
100 % der Grenze unzulässig. **Schwer nach unten** ist stabil, ignoriert aber die Häfen und braucht im Standard-Bay gut 26 Umstauungen. Wer beides zugleich optimiert, zahlt bis fast zur
Grenze des Möglichen nichts; erst ganz am strengen Ende (**die Kante**) entstehen einzelne Umstauungen. Jede Umstauung kostet zwei Kranspiele: die Stabilität hat einen messbaren
Preis in Kranzeit.

## Modell

Ein Bay aus C Stapeln und T Lagen, ein Ladehafen, Zielhäfen 1 bis P. Ein Container hat einen Zielhafen und eine von vier Gewichtsklassen; alle Container sind gleich groß und stehen ohne
Lücken. **Umstauungen** eines Containers = Zahl der verschiedenen Häfen unter ihm, die vor seinem eigenen angelaufen werden (das ist ein Relocation-Problem mit gewählter Platzierung).
**Schwerpunkt-Grenze:** Σ Gewicht × Lage ≤ L, angegeben als Anteil des Spielraums zwischen dem tiefstmöglichen Schwerpunkt (Gewicht zuerst) und dem der Zielhafen-Sortierung
(100 % = die Sortierung ist gerade erlaubt, 0 % = nur der tiefste Schwerpunkt); ganzzahlig gerechnet: L = kmin + ⌊p·(kpod − kmin)/100⌋. **Seitenneigung:** |Σ (2c − (C − 1)) · W_c| ≤ B mit
B = ⌊p·Gesamtgewicht·(C − 1)/100⌋. **Kranspiele = Container + 2 × Umstauungen**, mit 30 Spielen je Stunde als Annahme. Formal im Expander „📐 Mathematische Formulierung".

## Methodik – vier Verfahren

Alle Verfahren stauen dieselben Container; Referenz aller Vergleiche ist **Gewicht zuerst**.

- **Zielhafen zuerst**: nach Zielhafen sortiert, der fernste unten. Null Umstauungen, Schwerpunkt so hoch wie möglich; unterhalb 100 % Grenze zulässig nur, wenn die Sortierung zufällig passt.
- **Gewicht zuerst**: schwerste unten. Der tiefstmögliche Schwerpunkt (bewiesen gegen Brute Force und eine analytische Untergrenze).
- **Sortieren + Reparatur** (eigene Heuristik): Start bei der Zielhafen-Sortierung, dann Tausche, die den Schwerpunkt unter die Grenze bringen und dabei möglichst wenig Umstauungen kosten;
  inkrementell gerechnet (identisch zur naiven Fassung, 7,5-mal schneller). Sie kann die Grenze verfehlen (dann steht „Grenze verletzt“) und ist in seltenen Fällen schlechter als Gewicht zuerst.
- **Exakt (CP-SAT)**: die kleinste Zahl von Umstauungen, die beide Grenzen einhält; Zeitlimit 4 s live, 30 s auf Knopfdruck. Ein Optimum von 0 ist per Definition bewiesen (kein Löser nötig);
  sonst steht ein Intervall aus unterer Schranke und bester Lösung, **nie ein unbewiesener Wert als Optimum**. „Keine zulässige Stauung“ wird erkannt und begründet.

Die **Stichprobe** (20 Ladelisten mit den Seeds 0 bis 19, nicht der eingestellte Seed) und die **Kurve** (Umstauungen über der Schwerpunkt-Grenze, 7 Grenzwerte × 8 Ladelisten) laufen auf Knopfdruck
mit Fortschrittsbalken (etwa 15 bis 90 s je nach Bay-Größe).

## Befunde (gemessen, keine Behauptungen)

Bay 8 × 6, Füllgrad 90 %, 5 Zielhäfen, Seitenneigung 2 %; Vorab-Messreihe in `hafen-planung/messreihe_stau/ERGEBNIS.md`, Presets in `tools/PRESET_SWEEP.md`.

| Frage | Befund |
|---|---|
| **Wie viel kostet Gewicht zuerst?** | 23 bis 27 Umstauungen (5 Häfen), bis 30 bei 7 Häfen; unabhängig von der Grenze. |
| **Warum nicht einfach nach Zielhafen?** | Unterhalb 100 % Grenze ist der Plan in **20 von 20** Ladelisten unzulässig. |
| **Was kostet die Optimierung?** | Kurve über die Grenze 0 / 10 / 20 / 30 / 50 / 75 / 100 %: **Exakt 2,6 / 0 / 0,1 / 0 / 0 / 0 / 0**, Reparatur 5,9 / 3,6 / 2,4 / 1,1 / 0,75 / 0,25 / 0 (Mittel über 8 Listen, 2 s Limit). Ab etwa 10 % der Grenze ist die Stabilität praktisch kostenlos; die Kante liegt bei 0 %. |
| **Lohnt sich der exakte Löser?** | Gegen Gewicht zuerst immer (26,3 gegen 0 bei 30 %). Gegen die Reparatur: 1,6 gegen 0 bei 30 % im Mittel, klar aber klein; die großen Lücken bestehen zu den einfachen Regeln. |
| **Wie weit reicht der Löser?** | 96 Container (12 × 8) bei 50 %: Median 1,3 s, alle bewiesen. Bei 0 % bleibt ein großer Teil der Listen im Limit unbewiesen (13 von 20 bei 2 s); dort steht ein Intervall. |
| **Ist die Reparatur zuverlässig?** | Nein: in etwa 10 % vergleichbarer Zufallsfälle verfehlt sie die Grenze (immer an einem echten lokalen Ende), und in 1 von 186 Fällen ist sie schlechter als Gewicht zuerst. Die Tests halten das fest. |
| **Presets** | Eine gemeinsame Ladeliste (Seed 31) für alle fünf; jede Kennzahl zwischen dem 10. und 90. Perzentil der Grundgesamtheit. „Am Limit“ liegt bei 0 %, nicht bei 10 %: bei 10 % ist das Optimum im Mittel nur 0,2. |

## Ehrliche Grenzen

- **Ein Bay, ein Ladehafen.** Kein Zu- und Aussteigen unterwegs, keine Reefer-Steckdosen, kein 20/40-Fuß-Unterschied, kein Gefahrgut, keine Stapelgewichtsgrenze, keine Lukendeckel.
- **Stabilität als Summe Gewicht × Lage plus Seitenmoment**, keine Klassifikationsrechnung eines Schiffs. Die Kranspiele je Stunde sind eine Annahme.
- **Die Reparatur-Heuristik ist meine eigene Konstruktion**; der Abstand zum Optimum ist klein (0,5 bis 3 Umstauungen) und wird so erzählt.
- Alle Zahlen sind **Größenordnungen aus einer Simulation mit zufälligen Ladelisten, keine Messung an echten Bay-Plänen.**

## Design-Entscheidungen und Funde

**Die Grenze als Anteil des Spielraums.** Ein absoluter Schwerpunkt-Regler wäre je nach Bay wirkungslos oder unlösbar; der Anteil zwischen dem tiefsten und dem Zielhafen-sortierten Schwerpunkt
ist immer aussagekräftig. Beide Grenzen werden mit ganzzahliger Arithmetik gebildet (kein Runden nach Gleitkomma).

**Die Hauptansicht behauptet keine „beste Strategie“.** Vier Kennzahlen mit dem Unterschied zur Referenz; ein Plan, der eine Grenze verletzt, steht mit „⚠️“ und zählt nicht als Verbesserung (graues
Delta, nicht grün).

**Das Urteil kennt drei Zustände.** „Besser“, „schlechter“ und „kein klarer Unterschied“ (größer als zwei Standardfehler der gepaarten Differenz), jeweils mit dem Anteil der Ladelisten, in denen
es umgekehrt ist, und der Verteilung (besser / gleich / schlechter, Median gegen Mittel). Nur Ladelisten, in denen beide Verfahren zulässig sind, gehen ein.

**Beweislage vor Wert.** Der Exakt-Wert trägt „≤“, wenn das Optimum nicht bewiesen ist, und das Intervall steht im Tooltip. Ein „Optimum 0“ braucht keinen Löser; die Kante der Kurve
wird an bewiesenen und offenen Punkten sichtbar gemacht.

**„Am Limit“ wurde nach der Messung verschoben.** Der Plan sah 10 % vor; gemessen ist das Optimum dort im Mittel 0,2 und meist 0. Erst bei 0 % (nur der tiefste Schwerpunkt) kostet auch das
Optimum Umstauungen. Ein Preset soll das zeigen, was gemessen ist.

**Abnahmetests prüfen Schwellen nicht.** Über echte Daten getestet, liegen die Werte weit von den Schwellen; erst Tests mit künstlichen Werten, bei denen jedes Kriterium einzeln an seiner
Schwelle kippt, fangen Fehler an den Schwellen. Der Fehler-Einbau-Test deckte zudem eine Falle der Testumgebung auf: gleich lange Mutanten in derselben Sekunde ließen Python veralteten
Bytecode nutzen (Abhilfe: `PYTHONDONTWRITEBYTECODE=1`).

**Zeitlimit-Messungen schwanken mit der Rechenlast.** Bei überlasteter CPU bleiben Optima unbewiesen, die sonst in unter einer Sekunde bewiesen sind. Preset-Kriterien mit Optimum 0 sind davon
unabhängig; die anderen stehen mit Abstand zur Schwelle.

## Tests

`python -m pytest tests/ -v` – 1273 Tests, rund 8 Minuten. Zusammensetzung:

- **Regeln:** Umstauungen nach Formel gegen eine Simulation des Löschens Hafen für Hafen (300 Zufallsstapel), Gewicht zuerst gegen Brute Force und eine analytische Untergrenze, Zielhafen zuerst
  gegen das Brute-Force-Minimum, inkrementelle gegen naive Reparatur (120 Listen).
- **Exakt:** CP-SAT gegen Brute Force auf 300 Kleinstlisten (davon 100 mit strenger Grenze, mit Prüfung, dass positive Optima vorkommen), Unzulässigkeit, Grenzen inklusive, „Optimum ≤ jede Regel“,
  Monotonie in der Grenze, Zeitlimit-Pfade mit ersetztem Löser.
- **Auswertung:** Kennzahlen, Frontier gegen Direktrechnungen, Urteil in drei Zuständen und an der Schwelle, Verteilung besser / gleich / schlechter.
- **Figuren und Panels:** Bay-Bild aus den Ergebnisobjekten (Form je Container, roter Rand, Hover über das ganze Rechteck), Kennzahlen-Farben am Streamlit-Proto.
- **Presets:** Geschichte in der gezeigten Liste, im Mittel von 20 Listen, typisch je Kennzahl; Kriterien an ihren Schwellen mit künstlichen Werten.
- **PDF:** Inhalt Zelle für Zelle, genaue Sonderzeichen (fpdf2 stürzt bei „–“, „€“ und Emoji ab), Abschnitte nicht über Seitenumbrüche zerteilt.
- **End-to-End (AppTest):** Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, größtes und kleinstes Bay, Exakt ohne Plan und nicht bewiesen, Stichprobe und Kurve, Urteil in
  allen Zuständen, Exakt-Tab.

Zusätzlich wurde jedes Modul mit **eingebauten Fehlern** geprüft (über 300 Stück); die verbleibenden Überlebenden sind nachweislich gleichwertig oder betreffen reine Seitenumbruch-Schutzabstände.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar, Hauptansicht, Bay-Blick, Kernabschnitt, Methodenvergleich, Texte |
| `stau_constants.py` | Regler-Grenzen, `PRESETS`, Verfahren, Farben, feste Parameter (Gewichtsklassen, Kranspiele je Stunde, Zeitlimits) |
| `stau_presets.py` | `SETTING_SPECS`, Permalink (Begrenzen und Einrasten), Presets, Seed-Knopf |
| `stau_scenario.py` | Ladeliste aus den Reglern, Spielraum und Grenzen L und B (ganzzahlig) |
| `stau_rules.py` | Bewertung (Umstauungen, Schwerpunkt, Moment), Zielhafen zuerst, Gewicht zuerst, Reparatur (inkrementell), Ankunftsreihenfolge |
| `stau_exact.py` | CP-SAT-Modell, Zeitlimit, Intervall, Abkürzung bei Optimum 0 |
| `stau_evaluation.py` | Kennzahlen je Verfahren, Stichprobe, Frontier, gepaarte Differenz, Verteilung, Urteil |
| `stau_visualization.py` | Bay-Bild, Frontier, Verteilung, Vergleich (alle Achsen fest) |
| `stau_ui_panel.py` | Panel je Verfahren und Exakt-Tab |
| `stau_pdf_export.py` | PDF-Ergebnis (`fpdf2`, Kernschrift, Sonderzeichen-Bereinigung) |
| `stau_stories.py` | Abnahmekriterien der Presets (Quelle für Werkzeug und Tests) |
| `tools/tune_presets.py`, `tools/PRESET_SWEEP.md` | Preset-Abstimmung und ihr Bericht |
| `tests/` | siehe oben |

## Bewusst nicht umgesetzt (mögliche Erweiterungen)

- **Mehrere Ladehäfen** (Zu- und Aussteigen unterwegs), **Reefer-Steckdosen**, **20/40-Fuß**, **Gefahrgut-Trennung**, **Stapelgewichtsgrenze**, **Lukendeckel**.
- **Mehrere Bays** und Kranverteilung (Kopplung an die Kran-Demos), korrelierte Gewichte.
- **Kalibrierung an echten Bay-Plänen.**

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py population|seeds|pick`.

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von
[Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning.
Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
