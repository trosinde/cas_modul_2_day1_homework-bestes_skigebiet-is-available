# Proposal

## Why

~80% der Skigebiet-Preise sind geschätzt, weil skiresort.de nur für ~20% der Gebiete Preise liefert. Die bisherige Schätzmethode (Peer-Median pro Land+Grössenklasse) weist allen Gebieten einer Gruppe denselben Preis zu — z.B. bekamen 114 von 150 CH-Resorts den identischen Passpreis. Das führt zu irreführenden Visualisierungen (komprimierter Boxplot, echte Preise als "Ausreisser") und unterschätzt die Preisvariation innerhalb eines Landes.

Zusätzlich fehlte Transparenz: Nutzern war nicht erkennbar, wie viele Preise in einem Land geschätzt vs. gescrapt sind.

## What Changes

- **Preisschätzung per Log-Regression:** `impute_missing_prices()` verwendet log-lineare Regression (adult_pass ~ log(slope_km)) pro Land statt einheitlichem Gruppen-Median. Geschätzte Preise skalieren mit der Gebietsgrösse. Fallback auf Peer-Median bei <5 Datenpunkten pro Land.
- **Datenqualitäts-Warnung im Boxplot:** Das Dashboard zeigt "⚠ X% geschätzt" unter Ländern mit >50% geschätzten Preisen im Boxplot "Tageskosten je Land".
- **Reflexionsdokumentation:** Probleme mit LLM-fabrizierten Daten und fehlenden Preisdaten unter "Probleme unterwegs" dokumentiert.

## Capabilities

### New Capabilities

*(keine)*

### Modified Capabilities

- `resort-source`: Requirement "Price Scraping (Phase 3)" wird erweitert um Regressions-basierte Preisschätzung bei fehlenden Scraped-Preisen.
- `dashboard`: Requirement "Interactive Dashboard" wird erweitert um Datenqualitäts-Annotationen in Charts.

## Impact

- **components/resort_source/scraper.py** — Neue Funktion `_fit_price_regression()`, geändertes `impute_missing_prices()`
- **components/dashboard/template.html** — Boxplot-Annotation mit Schätz-Anteil pro Land
- **task6_reflection/reflection.md** — Zwei neue Einträge unter "Probleme unterwegs"
- **Daten:** Alle geschätzten Preise ändern sich (breitere Streuung), Ranking-Reihenfolge kann sich leicht verschieben
- **Keine API-Änderung, keine Schema-Änderung, keine neuen Abhängigkeiten**
