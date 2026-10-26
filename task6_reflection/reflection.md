## Reflexion und Vision

### Erlebte Herausforderungen

*Wird während der Arbeit ergänzt.*

### Probleme unterwegs

*Hier werden laufend Probleme und Überraschungen dokumentiert.*

- **C2 komplett LLM-fabriziert:** Alle Restaurantdaten (Namen, Koordinaten, Preise) stammten aus GPT-4o — kein einziger Wert aus einer echten Quelle. Für die Uni-Abgabe nicht tragbar. Lösung: OSM für Restaurantliste, Playwright + LLM-Extraktion für Speisekarten-Preise, Eurostat-Fallback für Restaurants ohne auffindbare Speisekarte.
- **Overpass-API nicht erreichbar:** Lokale Firewall blockiert Verbindung zur Overpass-API. Mitigation: Caching der Antworten, alternative Mirrors (lz4, kumi).
- **Nur ~40-50% der OSM-Restaurants haben Website-Tags:** Von den Restaurants mit Website haben wiederum nur ~30-40% auffindbare Speisekarten. Der Rest benötigt den länderspezifischen Statistik-Fallback (Eurostat). Lösung: Transparente Kennzeichnung über `price_source` und `is_estimate`.
- **cost_table-Schema-Verletzung:** `lunch_main_eur`/`lunch_drink_eur` aus dem Restaurant-Join blieben als Spalten im cost_table-DataFrame und verletzten `additionalProperties: false`. Fix: Zwischenspalten nach Berechnung von `lunch_cost_eur` droppen.

### Ein leistungsfähiges System für die Generierung meines Falls sollte …

- Attribute mit Skalen-Ankern interaktiv definieren und an 5 Items vorab testen
- Prompt-Versionen vergleichen
- Faktenwerte und Koordinaten per Websuche bzw. Kartendienst mit Quelle füllen
- Mehrfach-Runs und Modellvergleiche per Klick starten
- Neue Datenquellen andocken, ohne bestehende neu zu erzeugen

### Ein leistungsfähiges System für die Validierung meines Falls sollte …

- Unsicherheit je Zelle anzeigen
- Widersprüche zwischen Begründung und Score markieren
- Verknüpfungsregeln interaktiv einstellen und die Wirkung auf der Karte sofort zeigen
- Stichproben dort vorschlagen, wo die Unsicherheit am grössten ist
- Korrekturen in den Prompt zurückführen

### Vision

Datenquellen, Verknüpfungen, Quellen, Validierungsstand und Freigabe-Ampel je Attribut in einem System.
Fachliche Komponenten mit festen Schnittstellen und Herkunftsangaben als Grundlage für nachvollziehbare LLM-Daten.
