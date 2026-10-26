# Design

## Approach

Minimale Änderungen: Timestamps in den Pipeline-Runner, je ein `print()` in jede stille Komponente.

## Pipeline Runner Timestamps

In `pipeline/run_pipeline.py`:

```python
import time
from datetime import datetime

def _ts():
    return datetime.now().strftime("[%H:%M:%S]")
```

Im Step-Loop:
- Vor `core.run()`: `t0 = time.monotonic()`, print mit `_ts()` Prefix
- Nach `core.run()`: Dauer `time.monotonic() - t0`, print mit Timestamp + Dauer
- Pipeline-Start: `t_pipeline = time.monotonic()`
- Pipeline-Ende: `f"Pipeline complete. ({elapsed:.1f}s)"`

## Component Summaries

Jede Komponente hat die Werte bereits berechnet (für Logger oder DataFrame). Nur ein `print()` fehlt.

| Komponente | Stelle | Werte |
|------------|--------|-------|
| C2 gastro_source | `run()`, nach `_apply_country_fallback` wenn `not scrape_menus` | `len(restaurants)`, Anzahl unique Countries |
| C3 geo_matcher | `run()`, nach dem Matching-Loop | matched, ambiguous, unmatched (schon als Variablen) |
| C4 cost_model | `run()`, nach DataFrame-Erstellung | `len(df)`, `len(df[df["in_ranking"]])` |
| C5 clustering | `run()`, nach best-k Bestimmung | `best_k`, `best_score`, Cluster-Anzahl |
| C6 dashboard | `run()`, nach Figure-Export | Anzahl Figures |
| C7 validator | `run()`, am Ende | Sample: `len(sample_df)` / Validate: recommendation + Flags |

## Formatierung

Einrückung mit 2 Spaces (`  `) wie der Pipeline-Runner, damit die Summaries visuell unter ihrem Step stehen:

```
[14:32:19]  RUN  C3: geo_matcher
  180 matched, 12 ambiguous, 8 unmatched
[14:32:20]  OK   C3: geo_matcher (0.4s)
```
