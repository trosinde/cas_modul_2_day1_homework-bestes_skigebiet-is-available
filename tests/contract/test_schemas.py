"""Contract tests: validate all example files against their schemas."""

import csv
import json
import pytest
from pathlib import Path

import jsonschema

CONTRACTS_DIR = Path("contracts")
EXAMPLES_DIR = CONTRACTS_DIR / "examples"

SCHEMA_CSV_PAIRS = [
    ("resort_table", "resorts.csv"),
    ("resort_runs", "resorts_runs.csv"),
    ("restaurant_table", "restaurants.csv"),
    ("restaurant_runs", "restaurants_runs.csv"),
    ("matches", "matches.csv"),
    ("resort_lunch", "resort_lunch.csv"),
    ("cost_table", "resorts_costs.csv"),
    ("clusters", "clusters.csv"),
    ("merge_log", "resorts_merge_log.csv"),
    ("merge_log", "restaurants_merge_log.csv"),
]


def load_schema(schema_id: str) -> dict:
    path = CONTRACTS_DIR / f"{schema_id}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def csv_to_dicts(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                if v == "" or v is None:
                    cleaned[k] = None
                elif v == "true":
                    cleaned[k] = True
                elif v == "false":
                    cleaned[k] = False
                else:
                    try:
                        cleaned[k] = int(v)
                    except ValueError:
                        try:
                            cleaned[k] = float(v)
                        except ValueError:
                            cleaned[k] = v
            rows.append(cleaned)
        return rows


@pytest.mark.parametrize("schema_id,csv_file", SCHEMA_CSV_PAIRS)
def test_example_csv_validates(schema_id, csv_file):
    csv_path = EXAMPLES_DIR / csv_file
    if not csv_path.exists():
        pytest.skip(f"{csv_file} not found")

    schema = load_schema(schema_id)
    rows = csv_to_dicts(csv_path)
    assert len(rows) > 0, f"{csv_file} is empty"

    errors = []
    for i, row in enumerate(rows):
        try:
            jsonschema.validate(row, schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Row {i}: {e.message}")

    if errors:
        pytest.fail(f"{len(errors)} rows failed validation in {csv_file}:\n" + "\n".join(errors[:5]))


def test_example_llm_responses_are_valid_json():
    llm_dir = EXAMPLES_DIR / "llm_responses"
    if not llm_dir.exists():
        pytest.skip("No llm_responses directory")

    for path in llm_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name} is not a JSON object"
        has_records = "resorts" in data or "restaurants" in data or "items" in data
        assert has_records, f"{path.name} has no 'resorts', 'restaurants', or 'items' key"


def test_all_schemas_are_valid():
    for path in CONTRACTS_DIR.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in schema, f"{path.name} missing $schema"
        assert "type" in schema or "properties" in schema, f"{path.name} missing type/properties"
