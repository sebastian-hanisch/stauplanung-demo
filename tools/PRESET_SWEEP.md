# Preset-Abstimmung (AP 6)

Werkzeug: `tools/tune_presets.py` (Modi `population`, `seeds`, `pick`); Kriterien in `stau_stories.py`, Abnahme in `tests/test_preset_stories.py` (echte Daten) und `tests/test_stories.py`
(künstliche Werte an den Schwellen).

Messbasis: Bay 8 × 6, Füllgrad 90 %, Seitenneigung 2 %, Ladelisten mit den Seeds 0 bis 19 (Grundgesamtheit, 2 s Limit für den Löser) und 0 bis 59 (Suche nach dem Preset-Seed).

## Grundgesamtheit (20 Ladelisten je Preset)

| Preset | Einstellung | Gewicht zuerst | Reparatur | Exakt | Zielhafen zuerst |
|---|---|---|---|---|---|
| Locker | Grenze 100 %, 5 Häfen | 26,3 | 0 | 0 | zulässig in 20/20, 0 Umstauungen |
| Üblich | 60 %, 5 Häfen | 26,3 | 0,45 | 0 (bewiesen 20/20) | unzulässig in 20/20 |
| Knapp | 30 %, 5 Häfen | 26,3 | 1,6 | 0 (bewiesen 20/20) | unzulässig |
| Am Limit | **0 %**, 5 Häfen | 26,3 | 7,15 | 3,2 (13 von 20 nicht bewiesen, Obergrenze) | unzulässig |
| Viele Häfen | 30 %, 7 Häfen | 30,3 | 2,5 | Exakt besser als Reparatur in 16 von 20 Listen | unzulässig |

## Befunde und Abweichungen vom Plan

- **„Am Limit“ liegt bei 0 %, nicht bei 10 %.** Der Plan (Vorab-Messreihe) nannte für 10 % im Mittel 1,15 Umstauungen im Optimum. Mit dem gebauten Modell (Seitenneigung 2 %, Grenze ganzzahlig
  aus dem Spielraum) bewies der Löser bei 10 % in 17 von 20 Listen ein Optimum von im Mittel **0,2**, bei 5 % 0,65 und erst bei **0 %** 3,15 (8 von 20 bewiesen, 10 s). Bei 10 % bliebe die
  Geschichte „auch das Optimum kostet Umstauungen“ nicht tragfähig; bei 0 % (nur der tiefstmögliche Schwerpunkt) trägt sie: Exakt im Mittel 3,2, Reparatur 7,15.
- **Die Zeitlimit-Messung schwankt mit der Rechenlast.** Mit 16 gleichzeitigen Prozessen (je 8 Löser-Threads) blieben bei 2 s viele Optima unbewiesen (Exakt bei „Knapp“ im Mittel 0,6 statt
  0); mit 2 Prozessen trug alles. Das Werkzeug rechnet deshalb mit `max_workers=2`. Kriterien, die ein Optimum von 0 verlangen, hängen nicht von der Beweisdauer ab (eine 0 ist immer
  bewiesen), Kriterien mit „Exakt im Mittel ≥ 0,5“ und „Exakt besser als Reparatur in ≥ 70 % der Listen“ sind Obergrenzen-Aussagen und stehen deshalb mit Abstand zur Schwelle.
- **Viele Häfen: 70 % statt 80 %.** Die Schwelle „Exakt besser als Reparatur in ≥ 80 % der Listen“ lag bei genau 16 von 20 (80 %) und kippte mit der Beweisdauer; jetzt gilt 70 %.
- Das gemessene Optimum bei „Üblich“ und „Knapp“ ist immer 0: die Optimierung findet stabile Pläne ohne Umstauung, wo die einfachen Regeln 26 (Gewicht zuerst) beziehungsweise bis zu 3 (Reparatur) brauchen.

## Gewählt

- Eine gemeinsame Ladelistennummer für alle Presets: **Seed 31** (Bay 8 × 6, 90 %, Seitenneigung 2 %). Alle fünf Geschichten tragen an dieser Liste, auch mit 4 s Live-Limit und
  nach dem Beweis (`tests/test_preset_stories.py`); jede Kennzahl liegt zwischen dem 10. und 90. Perzentil der 20 Grundgesamtheits-Listen. Der Abstand zum Median (Summe der Logarithmen) ist bei
  Seed 31 1,3, bei Seed 0 0,7, Seed 43 1,1; Seed 31 blieb, weil an ihm alle Messreihen der Vorab-Untersuchung und alle festen Testwerte hängen.
- An Seed 31: Locker 27 / 0 / 0 / 0 (Gewicht / Reparatur / Exakt / Zielhafen), Üblich 27 / 0 / 0, Knapp 27 / 3 / 0, Am Limit 27 / 4 / **2 (bewiesen)**, Viele Häfen 28 / 2 / 0.
- Die „nicht bewiesen“-Anzeige zeigt „Am Limit“ nicht an dieser Liste (dort ist 2 in unter 1,3 s bewiesen), sondern in der Stichprobe und im Diagramm (offene Punkte bei 0 % und 20 %).
