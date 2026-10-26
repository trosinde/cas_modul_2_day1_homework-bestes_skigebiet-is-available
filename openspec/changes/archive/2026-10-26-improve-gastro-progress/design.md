# Design

## Context

See proposal.md for motivation. Currently `_extract_prices()` in `components/gastro_source/core.py` receives only the filtered list of restaurants with websites. It uses `len(restaurants)` as the denominator for both percentage and count display, which is correct for the iteration but lacks the total-restaurant context the user needs.

## Goals / Non-Goals

**Goals:**
- Show the user how far through the scrapable set (with website) they are
- Show the total restaurant count for context

**Non-Goals:**
- Changing any scraping logic or output format
- Adding a progress bar library

## Decisions

**Add `total_all` parameter to `_extract_prices()`** rather than computing it inside the function. The function only sees the filtered list; the caller (`run()`) knows the total count from before filtering. Passing it as a parameter keeps `_extract_prices` decoupled from the full restaurant list.

**Keep the German labels ("mit Website", "gesamt")** in the progress output, matching the user's preference and the project's German context.

## Risks / Trade-offs

No risks. The change is purely cosmetic (print output). No logic, data flow, or schema is affected.
