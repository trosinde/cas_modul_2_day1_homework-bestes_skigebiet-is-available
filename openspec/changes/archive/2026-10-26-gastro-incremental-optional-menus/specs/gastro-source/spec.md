# Spec Delta

## MODIFIED Requirements

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

### Requirement: Progress Display
The system SHALL show menu extraction progress with both the website-count and total restaurant count.

#### Scenario: Progress format during extraction
- **WHEN** extracting menu prices from restaurants with websites
- **THEN** display progress as `[X%] N/M mit Website | T gesamt | menu:A cached:C fallback:B err:D | ETA Xs | name` where M = restaurants with website, T = all restaurants, and the percentage refers to M

#### Scenario: Completion summary
- **WHEN** menu extraction finishes
- **THEN** display a summary including both counts and cached count: `M mit Website von T gesamt`
