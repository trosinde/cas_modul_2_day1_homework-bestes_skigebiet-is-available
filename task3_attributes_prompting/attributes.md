## Attribute und Prompting

### Skigebiete (C1)

Datenitem: ein zusammenhängendes, gemeinsam vermarktetes Liftgebiet mit eigenem Skipass.

| Attribut | Beschreibung | Typ | Prüfbar? |
|---|---|---|---|
| name | Offizieller Name | nominal | – |
| lat, lon | Koordinaten Talstation | quantitativ | ja |
| top_elevation_m | Höchster Liftpunkt | Verhältnis (m) | ja |
| base_elevation_m | Tiefster Liftpunkt | Verhältnis (m) | ja |
| slope_km | Pisten-km | Verhältnis (km) | ja (unscharf) |
| day_pass_adult_eur | Tageskarte Erwachsene | Verhältnis (EUR) | ja |
| day_pass_youth16_eur | Tageskarte 16 J. | Verhältnis (EUR) | ja |
| day_pass_child13_eur | Tageskarte 13 J. | Verhältnis (EUR) | ja |
| age_category_16/_13 | Alterskategorie | nominal | ja (wichtig!) |
| family_pass_eur | Familienkarte | Verhältnis (EUR) | ja |
| snow_reliability | Schneesicherheit | ordinal (1–10) | indirekt |
| family_friendliness | Familienfreundlichkeit | ordinal (1–10) | indirekt |
| drive_time_min | Fahrzeit ab Singen | Verhältnis (min) | ja |

Score-Anker: 1–3 schwach, 4–6 durchschnittlich, 7–8 gut, 9–10 Top 10 % der Alpen.

### Bergrestaurants (C2, ext1)

Datenitem: ein Restaurant im Skigebiet, das im Winter Skifahrer bewirtet.

| Attribut | Beschreibung | Typ | Prüfbar? |
|---|---|---|---|
| name | Restaurantname | nominal | ja |
| lat, lon | Lage | quantitativ | ja (Karte) |
| elevation_m | Höhe | Verhältnis (m) | ja |
| restaurant_type | Art | nominal | ja |
| lunch_main_eur | Hauptgericht | Verhältnis (EUR) | ja (Speisekarte) |
| lunch_drink_eur | Softdrink 0.5 l | Verhältnis (EUR) | ja |

### Prompts

Die Prompts liegen in `prompts/` und nutzen Platzhalter (`{{batch_list}}`, `{{chf_to_eur}}`).
Alle Prompts verlangen JSON-Rückgabe mit Schema-Validierung. Ein Systemprompt (`system.md`)
definiert die Grundregeln: nur EUR, WGS84-Koordinaten, Score-Anker, keine Erfindungen.

Siehe `contracts/` für die vollständigen JSON-Schemas und `prompts/` für die Prompt-Texte.
