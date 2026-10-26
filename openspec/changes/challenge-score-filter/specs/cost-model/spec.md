# Spec Delta

## ADDED Requirements

### Requirement: Challenge Score
The system SHALL compute a `challenge_score` (0–10) for each resort based on difficulty distribution, reflecting the resort's suitability for experienced skiers.

#### Scenario: Challenge score formula
- **WHEN** computing `challenge_score`
- **THEN** calculate `(adv_ratio * 0.5 + breadth * 0.3 + size_fac * 0.2) * 10` where `adv_ratio = (km_intermediate + km_advanced) / slope_km`, `breadth = count(tiers with km > 0) / 3`, `size_fac = min(slope_km / 30, 1.0)`

#### Scenario: Missing difficulty data
- **WHEN** a resort has no difficulty breakdown (all km values null or zero) but has slope_km > 0
- **THEN** set `challenge_score` to null

#### Scenario: Zero slope_km guard
- **WHEN** `slope_km` is null or zero
- **THEN** set `challenge_score` to null

## MODIFIED Requirements

### Requirement: Quality Score
The system SHALL compute a weighted quality score from LLM ratings, size, and challenge.

#### Scenario: Weighted sum
- **WHEN** computing quality_score
- **THEN** `weights.snow_reliability * snow_reliability + weights.family_friendliness * family_friendliness + weights.size_norm * size_norm * 10 + weights.challenge * challenge_score`
