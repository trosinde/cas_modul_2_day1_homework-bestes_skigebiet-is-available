# Tasks

## 1. Modify `_extract_prices()` signature and progress display

- [x] 1.1 Add `total_all: int = 0` parameter to `_extract_prices()` in `components/gastro_source/core.py:103`. Verify function signature is valid with `python -c "from components.gastro_source.core import run"`.
- [x] 1.2 Change progress print (line 133-138) from `[X%] i/total | menu:… | ETA…` to `[X%] i/M mit Website | T gesamt | menu:… | ETA…` where M = `total` (len of filtered list) and T = `total_all`. Verify by reading the changed line.
- [x] 1.3 Change completion summary (line 193-198) to include `M mit Website von T gesamt`. Verify by reading the changed line.

## 2. Pass `total_all` from `run()` call site

- [x] 2.1 Update the `_extract_prices(targets, cfg)` call in `run()` (line 252) to `_extract_prices(targets, cfg, total_all=len(restaurants))`. Verify by reading the changed line.

## 3. Verification

- [x] 3.1 Run `make test` and confirm all tests pass (no test changes needed — progress display is not covered by unit tests).
