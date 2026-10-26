## Pipeline-Beschreibung

### Architektur

Die Lösung besteht aus fachlich geschnittenen Komponenten mit festen Schnittstellen:

- **B1 llm_gateway**: Einziger LLM-Zugang mit Mock-Anbieter für Entwicklung
- **C1 resort_source**: Skigebietsdaten in 3 Runs holen und zusammenführen
- **C2 gastro_source** (ext1): Bergrestaurants je Region holen
- **C3 geo_matcher** (ext1): Restaurants über Koordinaten zuordnen
- **C4 cost_model**: Familienkosten, Qualitätswert, Preis-Leistungs-Index
- **C5 clustering**: k-Means und PCA
- **C6 dashboard**: Interaktive HTML-Seite mit Karte und Charts
- **C7 validator**: Stichprobe und automatische Prüfungen
- **C8 report_builder**: PDF-Bericht zusammenbauen

### Entscheidungen

| Entscheidung | Gewählt | Begründung |
|---|---|---|
| Bauweise | Fachliche Komponenten | Quellen unabhängig austauschbar |
| LLM-Zugang | Ein Gateway mit Mock | Eine Stelle für Wiederholung und Protokoll |
| Gastronomie | Eigene Quelle (C2) | Echte Unabhängigkeit, später durch echte Daten ersetzbar |
| Verknüpfung | Distanz zur Talstation | Koordinaten sind prüfbar, Namen uneinheitlich |
| Runs | 3 | Stabilität messbar |
| Summen | Im Code (C4) | Keine Rechenfehler, Parameter änderbar |

### Aufwand

- C1: ~37 LLM-Aufrufe (1 Liste + 12 Batches × 3 Runs)
- C2: ~98 LLM-Aufrufe (14 Regionslisten + 28 Batches × 3 Runs)
- Insgesamt wenige Franken
