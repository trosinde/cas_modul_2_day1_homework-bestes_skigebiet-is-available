# Skigebiete Familien-Ranking

## What this project does
LLM-generated dataset of Alpine ski resorts and mountain restaurants, ranked by value-for-money for a family day trip from Singen (Hohentwiel). Written Assignment for CAS Generative AI, University of Zurich.

## Architecture
Components communicate only via files in `contracts/` (except the llm_gateway API). Each component is a Python module under `components/` with its own `core.py`, `__main__.py`, `tests/`, and `README.md`.

## Working with this project
- `make mock-all` – run the full pipeline with mock LLM (no API cost)
- `make all` – run with real LLM
- `make test` – run all tests
- `make test-contracts` – validate schemas

## Rules
- Components talk only via files in contracts/ (except the llm_gateway API). No cross-imports between components.
- resort_source and gastro_source are independent: gastro_source never reads resort data. Linking only in geo_matcher, by coordinates.
- Use common.contract_io for all reads/writes; every output gets a .meta.json. Distances only via common/geo.py.
- Parameters only in config.yaml; no hard-coded paths, models or numbers.
- Develop and test against contracts/examples with provider: mock. Real API only in int1, int2, int3.
- Before any real LLM run: test with one batch (--limit-batches 1), show the output, wait for my OK.
- Ask before any run that calls the paid API more than 5 times.
- Never overwrite data/raw/. Never let the LLM compute totals.
- The gastronomy extension starts only after the go in int2 and must not touch data/raw/resort_source/.
- Fact-check target values come from me; never invent them.
- Charts as PNG to report/figures/ following the I8 naming rule.
- Append problems and surprises to task6_reflection/reflection.md under "Probleme unterwegs".
- Public repo: never commit .env or keys; run the secret check before every push. Push only after my OK.
- Implement changes with /opsx:apply (runs on Haiku), never via free text.
- Do not run "openspec update" without re-applying the model mapping afterwards.

## Interface changes
Need their own change with MODIFIED requirements; never change a schema silently.
