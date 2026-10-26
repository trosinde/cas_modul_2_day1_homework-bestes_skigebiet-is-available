# Tasks

## 1. Log-lineare Preisregression in scraper.py

- [x] 1.1 `_fit_price_regression()` implementieren: OLS pro Land auf log(slope_km) vs. adult_pass; Median-Ratios für youth/child/family; min_points=5. Verify: Unit-Test mit synthetischen Daten prüft Koeffizienten und Ratio-Berechnung.
- [x] 1.2 `impute_missing_prices()` umbauen: Regression bevorzugen, Fallback auf Peer-Median bei <5 Datenpunkten. Verify: `make resorts` läuft durch; CH geschätzte Preise streuen (min ≠ max); Log zeigt "Price regression CH: ... (n=29)".
- [x] 1.3 Test ergänzen: `components/resort_source/tests/` — Test dass Regression bei ausreichend Daten verschiedene Preise pro Gebiet liefert und Fallback bei wenigen Datenpunkten greift. Verify: `make test-resort-source` grün.

## 2. Datenqualitäts-Warnung im Dashboard

- [x] 2.1 Boxplot-Annotation in `template.html`: Für Länder mit >50% geschätzten Preisen "⚠ X% geschätzt" anzeigen. Verify: `make dashboard` läuft; Dashboard im Browser zeigt Warnung unter CH und AT.

## 3. Reflexion und Dokumentation

- [x] 3.1 `task6_reflection/reflection.md` ergänzen: Einträge zu LLM-fabrizierten Daten (4h Aufwand) und irreführendem Boxplot unter "Probleme unterwegs". Verify: Datei enthält beide Einträge.

## 4. Integration und Verifikation

- [x] 4.1 Volle Pipeline: `make resorts && make costs cluster dashboard`. Verify: Dashboard zeigt breitere Streuung im CH-Boxplot; Datenqualitäts-Warnung sichtbar; Top-10-Tabelle gefüllt.
- [x] 4.2 Tests: `make test` komplett grün. Verify: Exit-Code 0, keine Failures.
