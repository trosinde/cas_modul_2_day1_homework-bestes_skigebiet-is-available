# Tasks

## 1. Config and CLI

- [x] 1.1 Add `scrape_menus: false` to `config.yaml` in the `gastro:` section. Verify with `python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); assert c['gastro']['scrape_menus'] == False"`.
- [x] 1.2 Add `--scrape-menus` CLI flag (store_true) to `components/gastro_source/__main__.py` and override config when set. Verify by running `python3 -m components.gastro_source --help` and confirming the flag appears.

## 2. Incremental extraction cache

- [x] 2.1 Add `import json` to `components/gastro_source/core.py` if not present. Add `_load_cached_extraction(out_path: Path) -> dict | None` helper before `_extract_prices()`. Returns parsed data dict from a successful envelope, None otherwise. Verify with `python3 -c "from components.gastro_source.core import _load_cached_extraction"`.
- [x] 2.2 In `_extract_prices()`, move `out_path` construction before the `find_menu_page()` call is fine but the incremental check goes after `find_menu_page()` and before `extract_json()`: if `_load_cached_extraction(out_path)` returns data, populate the row from cache and `continue`. Add `n_cached = 0` counter. Verify by reading the changed code.
- [x] 2.3 Add `cached:{n_cached}` to the progress print line and the completion summary. Verify by reading the changed lines.

## 3. Optional menu scraping toggle

- [x] 3.1 In `run()`, replace `if not is_mock:` guard with `scrape_menus = cfg.get("gastro", {}).get("scrape_menus", False)` check. When false, log info and skip `_extract_prices()`. Verify by reading the changed code.

## 4. Makefile

- [x] 4.1 Update Makefile: default `gastro:` target without scraping, add `gastro-scrape:` target with `--scrape-menus`, ensure `gastro-test:` uses `--scrape-menus --menu-limit 5`. Verify by reading the Makefile.

## 5. Tests and verification

- [x] 5.1 Add unit tests for `_load_cached_extraction()` in `components/gastro_source/tests/test_core.py`: test with missing file, error envelope, valid envelope, corrupt file. Verify with `make test-gastro-source`.
- [x] 5.2 Run `make test` and confirm all tests pass (pre-existing `test_auto_no_keys` failure is known and unrelated).
