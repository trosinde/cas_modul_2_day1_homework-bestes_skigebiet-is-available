# Resort Source (C1) Specification

## Purpose

Fetches ski resort data from real, verifiable sources and enriches it with LLM-generated subjective ratings. Produces `data/processed/resorts.csv` conforming to `contracts/resort_table.schema.json`. No factual data may come from the LLM — only subjective ratings (snow_reliability, family_friendliness, value_for_money).

## Requirements

### Requirement: OpenSkiData Resort List (Phase 1)
The system SHALL download the ski area GeoJSON from OpenSkiData (`tiles.openskimap.org/geojson/ski_areas.geojson`) and extract downhill resorts for configured countries (CH, AT, DE, IT, FR).

#### Scenario: Cache hit
- **WHEN** `data/raw/resort_source/openskidata/ski_areas.geojson` exists
- **THEN** load from cache without re-downloading

#### Scenario: Fresh download
- **WHEN** cache file does not exist
- **THEN** download GeoJSON, cache it, extract resorts with: name, country, lat, lon, slope_km, top_elevation_m, base_elevation_m, lift_count, website

#### Scenario: Filtering
- **WHEN** extracting resorts
- **THEN** include only `activity: downhill`, `status: operating`, coordinates within Alpine bounds (lat 43–49, lon 4–17), and exclude Nordic patterns (Schanze, Loipe, Langlauf, etc.)

#### Scenario: Deduplication
- **WHEN** two resorts have the same normalized name within 5 km
- **THEN** keep only one

### Requirement: OSRM Driving Routes (Phase 2)
The system SHALL fetch real driving distances and times from the OSRM public API for all resorts from the configured origin (Singen).

#### Scenario: Incremental fetching
- **WHEN** a resort's route is already cached in `data/raw/resort_source/osrm/routes.json`
- **THEN** skip it and use cached data

#### Scenario: Parallel fetching
- **WHEN** fetching missing routes
- **THEN** use up to 8 parallel threads with progress display per country

#### Scenario: Reachability filter
- **WHEN** a resort's drive time exceeds `costs.max_drive_time_min` (default 180)
- **THEN** exclude it from further processing

### Requirement: Price Scraping (Phase 3)
The system SHALL scrape day pass prices from skiresort.de using Playwright (headless Chromium).

#### Scenario: URL pattern
- **WHEN** scraping a resort's prices
- **THEN** navigate to `skiresort.de/skigebiet/{slug}/` (overview page, NOT `/liftkartenpreise/`)

#### Scenario: Price parsing
- **WHEN** the page contains a tab-separated table with header row containing "Erwachsene", "Jugendliche", "Kinder"
- **THEN** extract EUR prices (preferred) or CHF prices (converted via config rate) for adult, youth, child

#### Scenario: Parallel scraping
- **WHEN** scraping multiple resorts
- **THEN** run one Chromium instance per country in parallel threads

#### Scenario: Incremental caching
- **WHEN** a resort's scrape result exists in `data/raw/resort_source/scraper/{resort_id}.json`
- **THEN** skip it and use cached data

#### Scenario: Missing prices imputation
- **WHEN** a resort has no scraped price
- **THEN** estimate using the median price of same-country, same-size-class resorts; mark `source_prices` as `"estimated:country_size_median"`

#### Scenario: Scraping report
- **WHEN** scraping completes
- **THEN** write `data/processed/scraping_report.csv` conforming to `contracts/scraping_report.schema.json` with status per resort (scraped, estimated, not_found, no_prices, error)

#### Scenario: Provenance chart
- **WHEN** scraping report is written
- **THEN** generate `report/figures/fig_data_provenance.png` showing price source breakdown per country

### Requirement: LLM Subjective Ratings (Phase 4)
The system SHALL use the configured LLM provider to generate subjective ratings for each resort. The LLM must NOT generate or override any factual data.

#### Scenario: Batch processing
- **WHEN** rating resorts
- **THEN** send batches of `resorts.batch_size` (default 10) resorts per LLM call, using prompt template `prompts/resort_ratings.md`

#### Scenario: Multiple runs
- **WHEN** `llm.runs` > 1 (default 3)
- **THEN** run multiple independent rating passes and merge via median (numeric) / mode (categorical)

#### Scenario: Rating record validation
- **WHEN** LLM returns a rating record
- **THEN** validate against `contracts/resort_rating_record.schema.json`; discard invalid records

#### Scenario: Cached batches
- **WHEN** `data/raw/resort_source/resort_ratings_run{n}/batch{i}.json` exists
- **THEN** load from cache without re-calling the LLM

### Requirement: Resort Table Output (Phase 5)
The system SHALL merge all phases into `data/processed/resorts.csv` conforming to `contracts/resort_table.schema.json`.

#### Scenario: Source traceability
- **WHEN** writing a resort row
- **THEN** set `source_coords=openskidata`, `source_driving=osrm`, `source_prices={URL or "estimated:country_size_median" or null}`, `source_physical=openskidata`, `source_ratings=llm`

#### Scenario: Real data stability
- **WHEN** writing real data fields (coordinates, prices, distances, elevations)
- **THEN** set `_sd=0.0` and `_range=0.0` (no variance — these are exact values)

#### Scenario: Minimum items
- **WHEN** fewer than `resorts.min_items` (default 100) resorts remain after all phases
- **THEN** exit with code 3
