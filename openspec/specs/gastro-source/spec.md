# Gastro Source (C2) Specification

## Purpose

Fetches mountain restaurant data from OpenStreetMap and enriches with lunch prices (from menu scraping or country-level estimates). Produces `data/processed/restaurants.csv` conforming to `contracts/restaurant_table.schema.json`. Independent of C1 — never reads resort data.

## Requirements

### Requirement: OSM Restaurant Fetch
The system SHALL query OpenStreetMap (Overpass API) for mountain restaurants in configured search regions.

#### Scenario: Region-based queries
- **WHEN** fetching restaurants
- **THEN** query each region defined in `config.gastro.search_regions` separately

#### Scenario: OSM caching
- **WHEN** a region's OSM response is already cached in `config.gastro.osm_cache_dir`
- **THEN** use cached data without re-querying

#### Scenario: Restaurant fields
- **WHEN** extracting a restaurant from OSM
- **THEN** include: name, country, region, lat, lon, elevation_m, restaurant_type, ski_area_hint, osm_id, osm_type, website

### Requirement: Lunch Price Determination
The system SHALL determine lunch prices per restaurant, preferring real menu data over estimates.

#### Scenario: Menu scraping toggle
- **WHEN** `config.gastro.scrape_menus` is false (default)
- **THEN** skip all menu extraction; every restaurant keeps its country fallback price

#### Scenario: Menu scraping
- **WHEN** `config.gastro.scrape_menus` is true AND a restaurant has a website with a readable menu
- **THEN** extract prices via LLM (`prompts/gastro_menu_extract.md`), compute lunch_main_eur using `config.gastro.price_method` (default: lower_half_avg), set `price_source=menu_card`

#### Scenario: Incremental menu extraction
- **WHEN** a restaurant's extraction envelope (`menu_extractions/{restaurant_id}.json`) already exists with `error: null` and valid `raw_response` JSON
- **THEN** load prices from the cached envelope without calling the LLM again

#### Scenario: Failed extraction retry
- **WHEN** a restaurant's extraction envelope has a non-null `error` field (e.g. API quota exceeded)
- **THEN** discard the cached result and retry the LLM extraction

#### Scenario: Country fallback
- **WHEN** no menu prices can be determined
- **THEN** use country-level average from `config.gastro.country_avg_prices` (Eurostat source), set `price_source=country_statistics_estimate`, `is_estimate=true`

#### Scenario: CLI override
- **WHEN** `--scrape-menus` CLI flag is passed
- **THEN** override `config.gastro.scrape_menus` to true for this run

### Requirement: Restaurant Table Output
The system SHALL write `data/processed/restaurants.csv` conforming to `contracts/restaurant_table.schema.json`.

#### Scenario: Schema fields
- **WHEN** writing a restaurant row
- **THEN** include all fields from schema: restaurant_id, name, country, region, lat, lon, elevation_m, restaurant_type, ski_area_hint, osm_id, osm_type, website, lunch_main_eur, lunch_drink_eur, price_source, is_estimate, menu_url, price_source_detail, price_level, confidence, reason_price, lunch_main_eur_sd, n_runs_valid

#### Scenario: Minimum items
- **WHEN** configured `gastro.min_items` is not reached
- **THEN** log warning but continue (do not fail)

### Requirement: Progress Display
The system SHALL show menu extraction progress with both the website-count and total restaurant count.

#### Scenario: Progress format during extraction
- **WHEN** extracting menu prices from restaurants with websites
- **THEN** display progress as `[X%] N/M mit Website | T gesamt | menu:A cached:C fallback:B err:D | ETA Xs | name` where M = restaurants with website, T = all restaurants, and the percentage refers to M

#### Scenario: Completion summary
- **WHEN** menu extraction finishes
- **THEN** display a summary including both counts and cached count: `M mit Website von T gesamt`
