# Cost Model (C4) Specification

## Purpose

Computes family day costs, quality scores, value indices, and rankings. Reads `resorts.csv` (C1) and optionally `resort_lunch.csv` (C3). Produces `data/processed/resorts_costs.csv` conforming to `contracts/cost_table.schema.json`.

## Requirements

### Requirement: Family Pass Cost
The system SHALL compute the cheapest option between individual tickets and family pass.

#### Scenario: Individual sum
- **WHEN** computing family pass cost
- **THEN** calculate `2 * adult + youth16 + child13`

#### Scenario: Family pass available
- **WHEN** `family_pass_eur` is not null and cheaper than individual sum
- **THEN** use `family_pass_eur` and set `family_pass_used=true`

### Requirement: Three Cost Variants
The system SHALL compute three cost variants, always all three.

#### Scenario: V1 — lift pass only
- **WHEN** computing day_cost_v1_eur
- **THEN** `family_pass_cost_eur`

#### Scenario: V2 — with travel
- **WHEN** computing day_cost_v2_eur
- **THEN** `family_pass_cost_eur + 2 * drive_distance_km * cost_per_km`

#### Scenario: V3 — with lunch
- **WHEN** resort_lunch data is available
- **THEN** `day_cost_v2_eur + 4 * (lunch_main_eur + lunch_drink_eur)`

### Requirement: Quality Score
The system SHALL compute a weighted quality score from LLM ratings and size.

#### Scenario: Weighted sum
- **WHEN** computing quality_score
- **THEN** `weights.snow_reliability * snow_reliability + weights.family_friendliness * family_friendliness + weights.size_norm * size_norm * 10`

### Requirement: Value Index and Ranking
The system SHALL compute value indices and rank resorts.

#### Scenario: Value index formula
- **WHEN** computing value_index
- **THEN** `quality_score / (family_day_cost_eur / 100)`

#### Scenario: Ranking eligibility
- **WHEN** determining `in_ranking`
- **THEN** require `drive_time_min <= max_drive_time_min` AND `n_runs_valid >= 2`

#### Scenario: Value rank
- **WHEN** a resort is `in_ranking=true`
- **THEN** rank by `value_index` descending (rank 1 = best value)
