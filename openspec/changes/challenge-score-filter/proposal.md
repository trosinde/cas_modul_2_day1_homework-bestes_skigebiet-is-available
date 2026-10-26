# Proposal

## Why

The dashboard ranks ski resorts by value-for-money, but ghost entries (0 lifts, e.g. a 2.8 km Ski Arlberg fragment) pollute the ranking, and small beginner-only resorts score high despite offering nothing for this family of experienced skiers. "Anspruch" (challenge) is a core search criterion — the family needs resorts with intermediate and advanced runs, not nursery slopes.

## What Changes

- **Lift-count fix**: Replace broken `liftCount` field (always 0) with sum from `lifts.byType[*].count`
- **0-lift filter**: Skip resorts with 0 lifts during extraction (ghost entries)
- **Difficulty breakdown**: Extract per-difficulty run counts and km from OpenSkiData (easy+novice, intermediate, advanced+expert+freeride+extreme)
- **Schema extension**: Add `lift_count`, `n_runs_easy/intermediate/advanced`, `km_easy/intermediate/advanced`, `challenge_score` to `resort_table.schema.json` (**BREAKING**: new required contract columns)
- **`challenge_score`**: New 0–10 score in cost model weighting advanced-run ratio (0.5), difficulty breadth (0.3), and minimum size (0.2)
- **Quality weights**: Rebalance to `challenge: 0.35, snow: 0.25, size: 0.25, family: 0.15` — challenge is the dominant factor
- **Dashboard**: Show `challenge_score` in Top 10 table

## Capabilities

### New Capabilities

_None_

### Modified Capabilities

- `resort-source`: Add difficulty breakdown extraction, fix lift count, filter 0-lift entries, pass new columns through to output
- `cost-model`: Add `challenge_score` computation, integrate into quality score with new weight configuration
- `dashboard`: Display challenge score and difficulty distribution in Top 10 table

## Impact

- `components/resort_source/osm.py` — extraction logic
- `components/resort_source/core.py` — column passthrough (drop_cols)
- `components/cost_model/core.py` — challenge_score + quality_score formula
- `contracts/resort_table.schema.json` — new columns (interface change)
- `config.yaml` — quality.weights
- `components/dashboard/template.html` — Top 10 display
- Pipeline re-run required after changes; resort count will drop (0-lift entries removed)
