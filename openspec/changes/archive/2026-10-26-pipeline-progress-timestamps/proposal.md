# Proposal

## Why

Die Pipeline-Ausgabe (`make all`) zeigt pro Schritt nur `RUN`/`OK`/`FAIL` ohne Zeitstempel und ohne Dauer. C3–C7 sind komplett stumm — der User sieht nicht, was passiert ist oder wie lange es gedauert hat. Für Debug und Monitoring braucht jeder Schritt sichtbaren Fortschritt und Zeitinformation.

## What Changes

- **Pipeline Runner**: `[HH:MM:SS]` Zeitstempel-Prefix bei `RUN`/`OK`/`FAIL`/`SKIP`, Dauer `(Xs)` bei OK/FAIL, Gesamtdauer am Ende
- **C3 geo_matcher**: Summary-Print mit Match-Statistik (matched, ambiguous, unmatched)
- **C4 cost_model**: Summary-Print mit Skigebiet-Anzahl
- **C5 clustering**: Summary-Print mit bestem k und Cluster-Anzahl
- **C6 dashboard**: Summary-Print mit Anzahl exportierter Figures
- **C7 validator**: Summary-Print mit Sample/Validierungs-Ergebnis
- **C2 gastro_source**: Summary-Print wenn Menu-Scraping deaktiviert (bisher stumm)

## Capabilities

### New Capabilities

_Keine_

### Modified Capabilities

- `pipeline`: Neue Requirements für Zeitstempel-Ausgabe und Fortschrittsanzeige aller Komponenten

## Impact

- `pipeline/run_pipeline.py` — Timestamp-Logik
- `components/geo_matcher/core.py` — Summary-Print
- `components/cost_model/core.py` — Summary-Print
- `components/clustering/core.py` — Summary-Print
- `components/dashboard/core.py` — Summary-Print
- `components/validator/core.py` — Summary-Print
- `components/gastro_source/core.py` — Fallback-Summary
