# Proposal

## Why

The menu extraction progress display in C2 (gastro_source) iterates only over restaurants with a website, but the progress line shows the total restaurant count as the denominator. This makes the percentage misleading (e.g. `[0.4%] 21/4791` when only 341 of 4791 have a website). The user needs to see both: how far through the scrapable set, and how many restaurants exist overall.

## What Changes

- Modify `_extract_prices()` to accept a `total_all` parameter representing the total restaurant count (including those without website).
- Change the progress line format from `[X%] i/total | …` to `[X%] i/M mit Website | T gesamt | …` where M = restaurants with website (the actual iteration set) and T = all restaurants.
- Update the completion summary to show both counts as well.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `gastro-source`: Adding a new requirement "Progress Display" specifying the dual-count progress format during menu extraction.

## Impact

- **Code**: `components/gastro_source/core.py` — `_extract_prices()` signature and two print statements, plus the call site in `run()`.
- **No schema, API, or dependency changes.**
