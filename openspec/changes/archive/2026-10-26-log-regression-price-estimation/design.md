# Design

## Context

Siehe proposal.md – Why. Die Preisschätzung (`impute_missing_prices` in `components/resort_source/scraper.py`) verwendet bisher einen fixen Median pro Land+Grössenklasse-Gruppe. Bei wenigen gescrapten Datenpunkten pro Gruppe bekommen viele Resorts identische Preise. Das Dashboard (`components/dashboard/template.html`) zeigt keine Information über den Anteil geschätzter Daten.

## Goals / Non-Goals

**Goals:**
- Geschätzte Preise sollen mit der Gebietsgrösse (slope_km) skalieren
- Datenqualität soll im Dashboard sichtbar sein

**Non-Goals:**
- Kein neues Scraping (die Quellenlage bei skiresort.de ändert sich nicht)
- Keine neue Schema-Felder (source_prices-Werte bleiben kompatibel)

## Decisions

### 1. Log-lineare Regression statt Gruppen-Median

**Wahl:** `adult_pass = a × log(slope_km) + b` pro Land, via OLS.

**Warum:** Korrelation log(slope_km) vs. Preis = 0.79 über alle gescrapten Daten. Log-Transformation fängt den abnehmenden Grenznutzen ab (doppelte Pistenlänge ≠ doppelter Preis).

**Alternativen:**
- *Gruppen-Median (Status quo):* Alle Resorts einer Gruppe bekommen identischen Preis → verzerrt Boxplots
- *Regionale Gruppierung:* Zu wenige gescrapte Datenpunkte pro Region (oft 0–2)
- *Nichtlineare Regression (Polynom, Spline):* Overfitting bei nur 5–29 Datenpunkten pro Land

**Schwellwert:** Minimum 5 gescrapte Datenpunkte pro Land für Regression. Darunter Fallback auf Peer-Median.

### 2. Preisableitungen über Median-Ratio

**Wahl:** youth/child/family-Preise = adult_predicted × median(field/adult) aus gescrapten Daten des Landes.

**Warum:** Die Verhältnisse (z.B. Jugend = 80% von Erwachsen) sind innerhalb eines Landes stabiler als absolute Preise. Separate Regressionen pro Feld wären bei wenigen Datenpunkten instabil.

### 3. Plotly-Annotation statt separatem UI-Element

**Wahl:** `Plotly.newPlot` annotations-Array mit Text-Labels unter dem Boxplot.

**Warum:** Kein zusätzliches HTML nötig, die Warnung bewegt sich mit den Daten, und sie erscheint nur bei betroffenen Ländern (>50% geschätzt).

## Risks / Trade-offs

- **[Regression-Ausreisser]** Ein einzelner extremer Scraping-Wert kann die Regressionslinie verzerren → Mitigation: Bei nur 5 Datenpunkten ohnehin vorsichtig; robustere Methoden (z.B. Huber) wären Overengineering für den Datensatz.
- **[Preis-Floor]** Die Regression kann negative Preise für sehr kleine Gebiete liefern → Mitigation: `max(predicted, 5.0)` als Floor.
- **[Ranking-Verschiebung]** Geschätzte Preise ändern sich, daher auch Rankings → Akzeptiert: Das neue Ranking ist realistischer als das alte mit identischen Preisen.

## Open Questions

Keine — alle Entscheidungen sind getroffen und implementiert.
