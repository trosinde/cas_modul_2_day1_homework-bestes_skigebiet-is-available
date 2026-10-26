# Design

## Context

Das Dashboard (`components/dashboard/template.html`) hat eine Sidebar mit vier Filtern: Land (Dropdown), Grössenklasse (Dropdown), Max. Fahrzeit (Range-Slider mit Live-Wertanzeige), Kostenvariante (Dropdown). Die Funktion `getFiltered()` (Zeile 187) liest alle Filterwerte und gibt die gefilterte Resort-Liste zurück. `render()` ruft `getFiltered()` und aktualisiert Tabelle, Karte und Charts. Events: Dropdowns auf `change`, der Range-Slider auf `input` (Zeilen 508–509).

`challenge_score` und `km_easy/km_intermediate/km_advanced` sind seit dem letzten Change (`challenge-score-filter`) in `DASHBOARD_RESORT_FIELDS` enthalten und im Dashboard-JSON verfügbar.

## Goals / Non-Goals

**Goals:**
- "Min. Anspruch"-Slider in der Sidebar, der Gebiete mit niedrigem Challenge Score ausblendet
- Verständlicher Tooltip für die Spalte "Anspruch" (was sagt der Score aus, nicht wie er berechnet wird)
- Hover-Tooltip auf Challenge-Score-Zellen mit km-Aufteilung

**Non-Goals:**
- Kein neuer Sortier-Mechanismus (Tabelle sortiert weiterhin nach Value Index)
- Keine Backend-/Pipeline-Änderung

## Decisions

**Slider-Platzierung:** Zwischen "Grössenklasse" und "Max. Fahrzeit", weil es ein Suchkriterium ist (wie Fahrzeit), kein Darstellungsfilter (wie Kostenvariante).

**Range:** 0–10, Step 0.5, Default 0 (= kein Filter aktiv). Step 0.5 gibt genug Granularität ohne zu viele Stufen.

**Filter-Logik in `getFiltered()`:** Neue Zeile `if ((r.challenge_score || 0) < minChallenge) return false;` — analog zum Drive-Time-Filter. Resorts ohne Challenge Score (null) fallen bei minChallenge > 0 raus, was korrekt ist (kein Score = keine Schwierigkeitsdaten).

**Event-Wiring:** `input`-Event auf dem Slider (wie `filterDrive`), triggert `render()`.

**Tooltip-Text Spaltenüberschrift:** Beschreibt was der Score bedeutet: "Höher = anspruchsvolleres Gelände. Bewertet den Anteil roter und schwarzer Pisten, die Vielfalt der Schwierigkeitsgrade und die Gebietsgrösse. Daten aus OpenSkiData."

## Risks / Trade-offs

- Resorts ohne Schwierigkeitsdaten (challenge_score = null) verschwinden bei jedem Slider-Wert > 0. Das betrifft nur 5 von 272 Resorts und ist akzeptabel, da fehlende Daten hier "unbekannter Anspruch" bedeuten.
