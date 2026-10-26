# Tasks

## 1. Schema Extension

- [x] 1.1 Add new optional columns to `contracts/resort_table.schema.json`: `lift_count` (integer|null), `n_runs_easy` (integer|null), `n_runs_intermediate` (integer|null), `n_runs_advanced` (integer|null), `km_easy` (number|null), `km_intermediate` (number|null), `km_advanced` (number|null), `challenge_score` (number|null). Update `x-column-order`. Verify: `make test-contracts` passes.

## 2. Resort Extraction (osm.py)

- [x] 2.1 Fix lift count in `_extract_resorts()` at line 98: replace `stats.get("lifts", {}).get("liftCount", 0)` with sum of `count` from all entries in `statistics.lifts.byType`. Verify: run extraction for a known resort (e.g. Feldberg) and confirm lift_count > 0.
- [x] 2.2 Add 0-lift filter: after computing lift_count, `if lift_count == 0: continue` to skip ghost entries. Verify: Ski Arlberg 2.8km fragment no longer appears in output.
- [x] 2.3 Extract difficulty breakdown from `byDifficulty`: compute `n_runs_easy` (easy+novice count), `n_runs_intermediate` (intermediate count), `n_runs_advanced` (advanced+expert+freeride+extreme count), and corresponding `km_easy`, `km_intermediate`, `km_advanced`. Ignore `other`. Verify: Feldberg shows values across tiers; Laax shows all three tiers populated.

## 3. Resort Source Passthrough (core.py)

- [x] 3.1 Remove `lift_count` from `drop_cols` at line 399 in `components/resort_source/core.py`. Add new columns (`n_runs_easy`, `n_runs_intermediate`, `n_runs_advanced`, `km_easy`, `km_intermediate`, `km_advanced`) to the OSM data flow so they appear in `resorts.csv`. Verify: `resorts.csv` contains the new columns after running `python3 -m components.resort_source --provider mock`.

## 4. Challenge Score (cost_model/core.py)

- [x] 4.1 Add `challenge_score` computation in `compute_costs()` before the quality score block (line ~103): `adv_ratio = (km_intermediate + km_advanced) / slope_km`, `breadth = count(tiers with km > 0) / 3`, `size_fac = min(slope_km / 30, 1.0)`, `challenge_score = (adv_ratio * 0.5 + breadth * 0.3 + size_fac * 0.2) * 10`. Handle null/zero slope_km → null challenge_score. Verify: Laax-like resort scores ~8+, small easy-only resort scores <2.
- [x] 4.2 Add `challenge` weight to quality score formula at line 104: include `weights["challenge"] * challenge_score.fillna(0)` in the weighted sum. Verify: quality_score changes for resorts with high challenge_score.

## 5. Config Update

- [x] 5.1 Update `quality.weights` in `config.yaml` to: `snow_reliability: 0.25`, `family_friendliness: 0.15`, `challenge: 0.35`, `size_norm: 0.25`. Verify: weights sum to 1.0.

## 6. Dashboard

- [x] 6.1 Add `challenge_score` column (rounded to 1 decimal) to the Top 10 ranking table in `components/dashboard/template.html`. Add a difficulty distribution indicator showing easy/intermediate/advanced km per resort (e.g. colored bar segments or text). Verify: open dashboard in browser, Top 10 shows challenge_score and difficulty info.

## 7. Integration Verification

- [ ] 7.1 Run full pipeline: `python3 -m components.resort_source --provider mock && python3 -m components.cost_model && python3 -m components.clustering && python3 -m components.dashboard`. Verify: no errors, Ski Arlberg 2.8km/0-lift absent from resorts.csv, Top 10 favors large challenging resorts, `make test` passes.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review.
- Push commits after user OK (two prior commits + this change's work).
