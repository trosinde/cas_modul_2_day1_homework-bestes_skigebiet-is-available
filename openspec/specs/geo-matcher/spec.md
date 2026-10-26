# Geo Matcher (C3) Specification

## Purpose

Links restaurants to ski resorts by geographic proximity. Produces `data/processed/matches.csv` and `data/processed/resort_lunch.csv`. This is the only component that connects C1 and C2 data — matching is by coordinates only.

## Requirements

### Requirement: Coordinate-Based Matching
The system SHALL match each restaurant to the nearest resort using Haversine distance, respecting size-based radius thresholds.

#### Scenario: Radius by size class
- **WHEN** matching a restaurant to resorts
- **THEN** use radius from `config.matching.radius_km`: small (5 km), medium (8 km), large (15 km)

#### Scenario: Ambiguity detection
- **WHEN** two resorts are within `config.matching.ambiguity_km` (1 km) of each other for a restaurant
- **THEN** set `match_status=ambiguous` and record both resorts

#### Scenario: Unmatched restaurants
- **WHEN** no resort is within the matching radius
- **THEN** set `match_status=unmatched`

#### Scenario: Hint agreement
- **WHEN** a restaurant has a `ski_area_hint` from OSM
- **THEN** check if the matched resort name matches the hint and set `hint_agrees` accordingly

### Requirement: Matches Output
The system SHALL write `data/processed/matches.csv` conforming to `contracts/matches.schema.json`.

#### Scenario: Required fields
- **WHEN** writing a match row
- **THEN** include: restaurant_id, resort_id, distance_km, second_resort_id, second_distance_km, match_status, hint_agrees

### Requirement: Resort Lunch Aggregation
The system SHALL aggregate restaurant prices per resort into `data/processed/resort_lunch.csv` conforming to `contracts/resort_lunch.schema.json`.

#### Scenario: Matched resorts
- **WHEN** a resort has at least `config.matching.min_restaurants` (1) matched restaurants
- **THEN** compute median lunch_main_eur and lunch_drink_eur, set `lunch_source=matched`

#### Scenario: Unmatched resorts
- **WHEN** a resort has no matched restaurants
- **THEN** use country median from matched resorts, set `lunch_source=country_median`
