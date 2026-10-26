# Spec Delta

## MODIFIED Requirements

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

#### Scenario: Missing prices imputation via regression
- **WHEN** a resort has no scraped price and the country has ≥5 scraped resorts with known slope_km
- **THEN** estimate adult pass price using log-linear regression (adult_pass ~ log(slope_km)) fitted on the country's scraped data; derive youth, child, and family prices via median ratio to adult price from the same country; mark `source_prices` as `"estimated:country_size_median"`

#### Scenario: Missing prices imputation fallback
- **WHEN** a resort has no scraped price and the country has <5 scraped resorts with known slope_km
- **THEN** estimate using the median price of same-country, same-size-class resorts; mark `source_prices` as `"estimated:country_size_median"`

#### Scenario: Scraping report
- **WHEN** scraping completes
- **THEN** write `data/processed/scraping_report.csv` conforming to `contracts/scraping_report.schema.json` with status per resort (scraped, estimated, not_found, no_prices, error)

#### Scenario: Provenance chart
- **WHEN** scraping report is written
- **THEN** generate `report/figures/fig_data_provenance.png` showing price source breakdown per country
