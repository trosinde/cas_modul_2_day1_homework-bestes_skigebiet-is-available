# Design

## Context

See proposal.md for motivation. The LLM gateway's `extract_json()` saves result envelopes to `menu_extractions/{restaurant_id}.json` with fields: `kind`, `template_id`, `timestamp`, `provider`, `model`, `temperature`, `prompt_tokens`, `completion_tokens`, `records`, `raw_response`, `attempts`, `error`. On success `error` is null and `raw_response` contains the parsed menu data as JSON text. On failure (e.g. 429) `error` is non-null.

The Playwright menu scraper (`common/menu_scraper.py`) already caches results per URL hash in `menus/{md5}.json` and returns instantly on cache hit. Only the LLM call lacks incremental behavior.

## Goals / Non-Goals

**Goals:**
- Make menu scraping opt-in via `config.gastro.scrape_menus` (default false)
- Skip LLM calls for restaurants with existing successful extraction envelopes
- Retry failed envelopes (error != null)
- Provide CLI override `--scrape-menus`

**Non-Goals:**
- Cache TTL / staleness detection for menu scraper or extraction cache
- Forced retry of negative Playwright results (no menu found)
- Changing the LLM envelope format

## Decisions

**Incremental check placement: after `find_menu_page()`, before `extract_json()`.**
The Playwright cache already makes `find_menu_page()` fast on repeat calls (millisecond return). Placing the incremental check after it means we still get `menu_result.menu_url` for populating the row, avoiding the need to store `menu_url` in the LLM envelope. The expensive LLM call is the only thing skipped.

**New helper `_load_cached_extraction(out_path)` rather than inline check.**
Encapsulates validation logic (file exists? error null? raw_response valid JSON?) in one testable function. Returns parsed data dict or None.

**Config default `false` with CLI override.**
`--scrape-menus` sets `cfg["gastro"]["scrape_menus"] = True` after config load. No separate `--no-scrape-menus` needed since config default is already false.

## Risks / Trade-offs

**Risk:** Cached extraction may become stale if menus change.
**Mitigation:** Users can delete `menu_extractions/` to force full re-extraction. No TTL needed for this project's scope (one-time data collection).
