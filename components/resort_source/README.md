# C1 – resort_source

Fetches ski resort data from the LLM in two phases:

1. **Item list** – one call per country to get resort names (dedup by normalised name)
2. **Attributes** – 3 independent runs, each in batches of `batch_size`, to get all numeric and categorical attributes

## Interfaces

| Direction | ID  | File |
|-----------|-----|------|
| Reads     | I0  | `config.yaml` |
| Calls     | IA  | `llm_gateway.generate_json()` |
| Writes    | I1  | `data/processed/resorts.csv`, `resorts_runs.csv` |
| Writes    | I10 | `data/processed/resorts_merge_log.csv` |

## Usage

```bash
python -m components.resort_source --config config.yaml
python -m components.resort_source --config config.yaml --limit-batches 1
python -m components.resort_source --config config.yaml --run 2
```

## Exit codes

- 0 – success
- 2 – configuration or input error
- 3 – fewer than `resorts.min_items` valid resorts
- 4 – LLM/API error
