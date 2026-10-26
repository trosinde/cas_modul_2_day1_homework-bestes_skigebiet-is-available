# Design

## Context

See proposal.md for motivation. The pipeline extracts resorts from OpenSkiData GeoJSON, enriches with prices and LLM ratings, then computes a value index. The `liftCount` field in the GeoJSON is absent (always returns 0), and difficulty breakdown data (`byDifficulty`) is available but not extracted. The current quality score uses three factors: snow_reliability, family_friendliness, size_norm.

Key files: `osm.py` (extraction), `core.py` in resort_source (merge + output), `core.py` in cost_model (scores + ranking), `resort_table.schema.json` (contract), `config.yaml` (weights), `template.html` (dashboard).

## Goals / Non-Goals

**Goals:**
- Remove ghost entries (0 lifts) from the dataset
- Extract difficulty breakdown per resort from existing OpenSkiData data
- Compute a `challenge_score` that ranks resorts by suitability for experienced skiers
- Integrate challenge into the quality score as the dominant factor

**Non-Goals:**
- Changing the price estimation model or scraping logic
- Adding new data sources beyond what OpenSkiData already provides
- Reworking the LLM rating prompts (family_friendliness stays as-is, just reweighted)

## Decisions

### 1. Lift count: sum from byType vs. liftCount field

**Decision:** Sum `count` from all entries in `statistics.lifts.byType`.

**Why:** The top-level `liftCount` key does not exist in the GeoJSON data — it always returns 0 via `.get("liftCount", 0)`. The `byType` dict has 12 lift types (cable_car, chair_lift, drag_lift, etc.), each with a reliable `count`. No alternative — this is the only correct source.

### 2. Difficulty tier mapping: 3 tiers from 8 categories

**Decision:** Map to 3 tiers: easy (easy+novice), intermediate (intermediate), advanced (advanced+expert+freeride+extreme). Ignore `other`.

**Why:** The European color scheme (blue/red/black) maps naturally to 3 tiers. `novice` is pre-beginner (magic carpet areas), belongs with easy. `expert` and `freeride` are harder than advanced — grouping up captures "challenging" terrain. `other` (1452 resorts have it) is usually unmarked ski routes; including it would muddy the signal.

**Alternative:** 4 tiers (separating expert/freeride). Rejected: adds complexity with little ranking impact — few Alpine resorts have meaningful expert/freeride km.

### 3. Challenge score formula weights

**Decision:** `adv_ratio * 0.5 + breadth * 0.3 + size_fac * 0.2`

**Why:**
- `adv_ratio` (0.5): The fraction of non-easy terrain is the strongest signal for "Anspruch". A resort where 80% is intermediate/advanced is clearly more challenging than one that's 90% easy.
- `breadth` (0.3): Having all three difficulty levels means variety. A resort with only intermediate runs scores lower than one with intermediate + advanced.
- `size_fac` (0.2): `min(slope_km/30, 1.0)` — saturates at 30 km. Prevents a 2 km resort with one black run from scoring high. 30 km threshold: ~median of "interesting" resorts.

### 4. Quality weight rebalancing

**Decision:** challenge=0.35, snow=0.25, size=0.25, family=0.15

**Why:** The family are experienced skiers — challenge is what they're optimizing for. Family friendliness drops because they don't need beginner infrastructure, but stays non-zero (child discounts, accessibility still matter). Snow reliability and size keep moderate weight.

### 5. Schema columns: nullable

**Decision:** All new columns (`lift_count`, `n_runs_*`, `km_*`, `challenge_score`) are nullable (`["type", "null"]`).

**Why:** Some resorts may have lift data but no difficulty breakdown (or vice versa). Nullable avoids forcing defaults that could mislead the ranking.

## Risks / Trade-offs

- **Resort count drop:** Filtering 0-lift entries removes ~64 resorts (from ~283). Combined with the existing min_items=100 threshold this is safe, but should be verified after the pipeline runs.
- **challenge_score correlation with size:** Larger resorts tend to have more difficulty variety, so challenge_score partially correlates with size_norm. The 0.2 size_fac weight in challenge plus the separate size_norm weight means size is somewhat double-counted. Accepted: this matches the family's preferences (they want large, challenging resorts).
- **Null challenge_score:** Resorts with no difficulty data get null challenge_score, which means they score 0 on the challenge component. This penalizes them in the ranking — acceptable since no data likely means a very small or undocumented resort.
