# Spec Delta

## MODIFIED Requirements

### Requirement: OpenSkiData Resort List (Phase 1)
The system SHALL download the ski area GeoJSON from OpenSkiData (`tiles.openskimap.org/geojson/ski_areas.geojson`) and extract downhill resorts for configured countries (CH, AT, DE, IT, FR).

#### Scenario: Cache hit
- **WHEN** `data/raw/resort_source/openskidata/ski_areas.geojson` exists
- **THEN** load from cache without re-downloading

#### Scenario: Fresh download
- **WHEN** cache file does not exist
- **THEN** download GeoJSON, cache it, extract resorts with: name, country, lat, lon, slope_km, top_elevation_m, base_elevation_m, lift_count, website, n_runs_easy, n_runs_intermediate, n_runs_advanced, km_easy, km_intermediate, km_advanced

#### Scenario: Filtering
- **WHEN** extracting resorts
- **THEN** include only `activity: downhill`, `status: operating`, coordinates within Alpine bounds (lat 43–49, lon 4–17), exclude Nordic patterns (Schanze, Loipe, Langlauf, etc.), and exclude resorts with 0 lifts

#### Scenario: Deduplication
- **WHEN** two resorts have the same normalized name within 5 km
- **THEN** keep only one

#### Scenario: Lift count from lift types
- **WHEN** computing `lift_count`
- **THEN** sum `count` across all entries in `statistics.lifts.byType` (the top-level `liftCount` field does not exist in the data)

#### Scenario: Difficulty breakdown
- **WHEN** extracting difficulty data from `runs.byActivity.downhill.byDifficulty`
- **THEN** aggregate into three tiers: easy (easy + novice), intermediate (intermediate), advanced (advanced + expert + freeride + extreme); extract `count` as `n_runs_*` and `lengthInKm` as `km_*` per tier; ignore the `other` category

### Requirement: Resort Table Output (Phase 5)
The system SHALL merge all phases into `data/processed/resorts.csv` conforming to `contracts/resort_table.schema.json`.

#### Scenario: Source traceability
- **WHEN** writing a resort row
- **THEN** set `source_coords=openskidata`, `source_driving=osrm`, `source_prices={URL or "estimated:country_size_median" or null}`, `source_physical=openskidata`, `source_ratings=llm`

#### Scenario: Real data stability
- **WHEN** writing real data fields (coordinates, prices, distances, elevations, difficulty breakdown)
- **THEN** set `_sd=0.0` and `_range=0.0` (no variance — these are exact values)

#### Scenario: Minimum items
- **WHEN** fewer than `resorts.min_items` (default 100) resorts remain after all phases
- **THEN** exit with code 3

#### Scenario: New columns passthrough
- **WHEN** writing the resort table
- **THEN** include `lift_count`, `n_runs_easy`, `n_runs_intermediate`, `n_runs_advanced`, `km_easy`, `km_intermediate`, `km_advanced` from OpenSkiData extraction
