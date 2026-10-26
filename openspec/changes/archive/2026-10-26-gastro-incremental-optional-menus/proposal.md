# Proposal

## Why

Menu scraping (Playwright + LLM) is expensive in time and API cost. Currently it runs unconditionally for all non-mock runs and has no resume capability — if aborted mid-run, every restaurant's LLM extraction is re-executed from scratch even though results are saved to disk. The user wants country-level fallback prices as the default (fast, free), with menu scraping as an explicit opt-in. When enabled, scraping must be incremental: already-processed restaurants are loaded from their cached extraction files.

## What Changes

- Add `gastro.scrape_menus` config toggle (default: `false`). When false, all restaurants use country-level fallback prices only.
- Add `--scrape-menus` CLI flag to override the config toggle.
- Add incremental LLM extraction cache: before calling the LLM, check if `menu_extractions/{restaurant_id}.json` already contains a successful result and reuse it. Error envelopes (e.g. 429) are retried.
- Add `cached:N` counter to progress display.
- Update Makefile targets for the new default.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `gastro-source`: Modifying "Lunch Price Determination" to make menu scraping conditional on `gastro.scrape_menus` and add incremental extraction cache. Modifying "Progress Display" to include cached count.

## Impact

- **Code**: `components/gastro_source/core.py` (new helper + modified `_extract_prices` + modified `run()`), `components/gastro_source/__main__.py` (new CLI flag)
- **Config**: `config.yaml` — new `gastro.scrape_menus` field
- **Makefile**: Updated targets
- **No schema or contract changes.**
