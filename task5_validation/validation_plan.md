## Validierungsplan

### Fünf Prüfebenen

| Ebene | Prüfung | Methode | Umfang |
|---|---|---|---|
| Einzelwert | Stimmt der Wert? | Faktencheck (I6) | 12 Gebiete, 10 Restaurants, 15 Zuordnungen |
| Item | In sich stimmig? | Begründung vs. Score, Regeln | 20 manuell, Regeln für alle |
| Attribut | Stabil? | Streuung und Spearman über 3 Runs | alle |
| Verteilung | Plausibel? | Histogramme, Ausreisser | alle |
| Datensatz | Bekannte Zusammenhänge? | Korrelationen, Geo | alle |

### Abbruchkriterien

- Mindestens 80 % der Faktenwerte innerhalb der Toleranz
- Spearman zwischen Runs mindestens 0.7 je Score
- Kein erfundenes Gebiet in den Top 10
- Erwartete Korrelationen mit richtigem Vorzeichen
- Alterskategorien zu mindestens 80 % richtig
- Ab ext1: mindestens 80 % der Zuordnungen richtig, 70 % der Gebiete mit Restaurant
