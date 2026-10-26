# Proposal

## Why

Die Familie kann gut Skifahren und sucht gezielt anspruchsvolle Gebiete. Der Challenge Score wird bereits berechnet und in der Tabelle angezeigt, aber es fehlt die Möglichkeit, langweilige Gebiete per Filter auszublenden — wie es bei der Fahrzeit bereits geht. Ohne Filter muss man die gesamte Liste manuell durchsehen.

## What Changes

- **Neuer Sidebar-Filter "Min. Anspruch"**: Range-Slider (0–10, Schrittweite 0.5, Default 0) analog zum bestehenden "Max. Fahrzeit"-Slider. Filtert Skigebiete mit `challenge_score` unter dem Schwellwert aus Karte, Tabelle und allen Charts.
- **Überarbeiteter Tooltip**: Die Spaltenüberschrift "Anspruch" im Top-10-Ranking bekommt einen verständlicheren Tooltip, der erklärt was der Score aussagt (nicht wie er berechnet wird).
- **Hover-Tooltip auf Zellen**: Beim Hover über den Anspruch-Wert eines Skigebiets zeigt ein Tooltip die km-Aufteilung (blau/rot/schwarz).

## Capabilities

### New Capabilities

_Keine._

### Modified Capabilities

- `dashboard`: MODIFIED requirement "Interactive Dashboard" — Erweiterung um Challenge-Score-Filter in der Sidebar und überarbeitete Tooltips.

## Impact

- `components/dashboard/template.html` — Sidebar-HTML, `getFiltered()` Filterfunktion, Event-Listener, Tooltip-Texte
- Keine Schema-, Backend- oder Pipeline-Änderungen nötig (rein clientseitig)
