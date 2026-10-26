"""Tests for C2 gastro_source against example data."""

import pandas as pd
import pytest
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"


def test_example_restaurants_csv_exists():
    path = EXAMPLES / "restaurants.csv"
    if not path.exists():
        pytest.skip("Example restaurants.csv not yet created")
    df = pd.read_csv(path)
    assert len(df) == 10
    assert "restaurant_id" in df.columns
    assert "lat" in df.columns
    assert "lon" in df.columns
    assert df["lat"].notna().all()
    assert df["lon"].notna().all()


def test_example_restaurants_runs_csv_exists():
    path = EXAMPLES / "restaurants_runs.csv"
    if not path.exists():
        pytest.skip("Example restaurants_runs.csv not yet created")
    df = pd.read_csv(path)
    assert len(df) == 30  # 10 restaurants * 3 runs
    assert "restaurant_id" in df.columns
    assert "run" in df.columns


def test_restaurant_id_format():
    path = EXAMPLES / "restaurants.csv"
    if not path.exists():
        pytest.skip("Example restaurants.csv not yet created")
    df = pd.read_csv(path)
    for rid in df["restaurant_id"]:
        parts = rid.split("-")
        assert len(parts) >= 3, f"restaurant_id '{rid}' must have >=3 parts"
        assert parts[0].isalpha() and len(parts[0]) == 2, \
            f"restaurant_id '{rid}' must start with 2-letter country code"


def test_no_resort_data_dependency():
    """C2 must not import resort-related modules."""
    import ast
    core_path = Path(__file__).resolve().parents[1] / "core.py"
    source = core_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = ".".join(a.name for a in node.names)
            assert "resort_source" not in module, \
                "C2 must not import from resort_source"
