## Reflexion und Vision

### Erlebte Herausforderungen

*Wird während der Arbeit ergänzt.*

### Probleme unterwegs

*Hier werden laufend Probleme und Überraschungen dokumentiert.*

- **C2 komplett LLM-fabriziert:** Alle Restaurantdaten (Namen, Koordinaten, Preise) stammten aus GPT-4o — kein einziger Wert aus einer echten Quelle. Für die Uni-Abgabe nicht tragbar. Lösung: OSM für Restaurantliste, Playwright + LLM-Extraktion für Speisekarten-Preise, Eurostat-Fallback für Restaurants ohne auffindbare Speisekarte.
- **Overpass-API nicht erreichbar:** Lokale Firewall blockiert Verbindung zur Overpass-API. Mitigation: Caching der Antworten, alternative Mirrors (lz4, kumi).
- **Nur ~40-50% der OSM-Restaurants haben Website-Tags:** Von den Restaurants mit Website haben wiederum nur ~30-40% auffindbare Speisekarten. Der Rest benötigt den länderspezifischen Statistik-Fallback (Eurostat). Lösung: Transparente Kennzeichnung über `price_source` und `is_estimate`.
- **cost_table-Schema-Verletzung:** `lunch_main_eur`/`lunch_drink_eur` aus dem Restaurant-Join blieben als Spalten im cost_table-DataFrame und verletzten `additionalProperties: false`. Fix: Zwischenspalten nach Berechnung von `lunch_cost_eur` droppen.
- **C1 Rating-Daten komplett LLM-fabriziert (4h Aufwand):** Durch ungenaue Spezifikation beim Prompting hat das LLM sämtliche Fakten (Preise, Höhen, Pistenlängen) frei erfunden statt aus echten Quellen zu beziehen. Die generierten Werte sahen plausibel aus, waren aber nicht belegbar — für eine Uni-Abgabe nicht akzeptabel. Lösung: Echte Datenquellen angebunden (OpenSkiData für Koordinaten/Pisten, skiresort.de-Scraping für Preise, OSRM für Fahrzeiten), LLM nur noch für subjektive Bewertungen (Schneesicherheit, Familienfreundlichkeit, Preis-Leistung). Erkenntnis: Ohne explizite Trennung von Fakten und Meinungen im Prompt-Design generiert das LLM alles — und halluziniert dabei überzeugend.
- **79% der CH-Preise geschätzt, Boxplot irreführend:** Nur 31 von 150 Schweizer Skigebieten hatten gescrapte Echtwerte von skiresort.de. Die restlichen 119 bekamen per Peer-Median (Land+Grössenklasse) alle denselben Passpreis (32 EUR Erwachsen), was den Boxplot künstlich zusammenstauchte und echte Schweizer Preise als "Ausreisser" darstellte. Fix: Log-lineare Regression (Preis ~ log(Pistenlänge)) pro Land, sodass geschätzte Preise mit der Gebietsgrösse skalieren. Zusätzlich Datenqualitäts-Warnung im Chart wenn >50% der Preise geschätzt sind.

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
