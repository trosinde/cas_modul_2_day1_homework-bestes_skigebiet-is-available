"""Tests for C2 gastro_source (OSM + menu extraction pipeline)."""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from components.gastro_source.core import (
    MOCK_RESTAURANTS,
    _compute_lunch_price,
    _apply_country_fallback,
    _load_cached_extraction,
    _restaurant_row,
    run,
)


# ---------------------------------------------------------------------------
# _compute_lunch_price
# ---------------------------------------------------------------------------

class TestComputeLunchPrice:
    def test_six_items_lower_half_avg(self):
        items = [
            {"name": "A", "price_eur": 24.00},
            {"name": "B", "price_eur": 22.00},
            {"name": "C", "price_eur": 18.00},
            {"name": "D", "price_eur": 16.50},
            {"name": "E", "price_eur": 14.00},
            {"name": "F", "price_eur": 9.50},
        ]
        # sorted desc: [24, 22, 18, 16.5, 14, 9.5] → lower half [16.5, 14, 9.5]
        assert _compute_lunch_price(items) == 13.33

    def test_two_items(self):
        items = [{"name": "A", "price_eur": 20.0}, {"name": "B", "price_eur": 10.0}]
        # sorted desc [20, 10], lower half [10] → 10.0
        assert _compute_lunch_price(items) == 10.0

    def test_single_item(self):
        items = [{"name": "A", "price_eur": 15.0}]
        # 1 item: len//2 = 0, lower_half = [15.0]
        assert _compute_lunch_price(items) == 15.0

    def test_empty_returns_none(self):
        assert _compute_lunch_price([]) is None

    def test_skips_zero_and_none(self):
        items = [
            {"name": "A", "price_eur": 18.0},
            {"name": "B", "price_eur": 0},
            {"name": "C", "price_eur": None},
            {"name": "D", "price_eur": 12.0},
        ]
        # valid: [18, 12] → lower half [12] → 12.0
        assert _compute_lunch_price(items) == 12.0

    def test_odd_count(self):
        items = [
            {"name": "A", "price_eur": 30.0},
            {"name": "B", "price_eur": 20.0},
            {"name": "C", "price_eur": 10.0},
        ]
        # sorted desc [30, 20, 10], 3//2=1, lower_half = [20, 10] → 15.0
        assert _compute_lunch_price(items) == 15.0


# ---------------------------------------------------------------------------
# _load_cached_extraction
# ---------------------------------------------------------------------------

class TestLoadCachedExtraction:
    def test_missing_file(self, tmp_path):
        assert _load_cached_extraction(tmp_path / "nope.json") is None

    def test_error_envelope(self, tmp_path):
        p = tmp_path / "err.json"
        import json
        p.write_text(json.dumps({
            "error": "Error code: 429 - credit_balance_exhausted",
            "raw_response": "",
        }))
        assert _load_cached_extraction(p) is None

    def test_valid_envelope(self, tmp_path):
        p = tmp_path / "ok.json"
        import json
        data = {"items": [{"name": "Schnitzel", "price_eur": 18.0}], "drink_05l_eur": 4.5}
        p.write_text(json.dumps({
            "error": None,
            "raw_response": json.dumps(data),
        }))
        result = _load_cached_extraction(p)
        assert result is not None
        assert result["items"][0]["price_eur"] == 18.0
        assert result["drink_05l_eur"] == 4.5

    def test_corrupt_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json at all {{{{")
        assert _load_cached_extraction(p) is None

    def test_empty_raw_response(self, tmp_path):
        p = tmp_path / "empty_raw.json"
        import json
        p.write_text(json.dumps({"error": None, "raw_response": ""}))
        assert _load_cached_extraction(p) is None

    def test_unparseable_raw_response(self, tmp_path):
        p = tmp_path / "bad_raw.json"
        import json
        p.write_text(json.dumps({"error": None, "raw_response": "not-json"}))
        assert _load_cached_extraction(p) is None


# ---------------------------------------------------------------------------
# _apply_country_fallback
# ---------------------------------------------------------------------------

class TestApplyCountryFallback:
    CFG = {
        "gastro": {
            "country_avg_prices": {
                "source": "Eurostat 2024",
                "CH": {"lunch_main_eur": 25.0, "lunch_drink_eur": 5.5},
                "AT": {"lunch_main_eur": 16.0, "lunch_drink_eur": 4.5},
            }
        }
    }

    def test_sets_estimate_fields(self):
        row = {"country": "CH", "lunch_main_eur": None, "is_estimate": None}
        _apply_country_fallback(row, self.CFG)
        assert row["lunch_main_eur"] == 25.0
        assert row["lunch_drink_eur"] == 5.5
        assert row["price_source"] == "country_statistics_estimate"
        assert row["is_estimate"] is True
        assert row["price_source_detail"] == "Eurostat 2024"

    def test_unknown_country_leaves_none(self):
        row = {"country": "XX", "lunch_main_eur": None, "price_source": None, "is_estimate": None}
        _apply_country_fallback(row, self.CFG)
        assert row["lunch_main_eur"] is None
        assert row["price_source"] is None


# ---------------------------------------------------------------------------
# _restaurant_row
# ---------------------------------------------------------------------------

class TestRestaurantRow:
    def test_all_schema_fields_present(self):
        rec = MOCK_RESTAURANTS[0]
        row = _restaurant_row(rec)
        expected_keys = {
            "name", "country", "region", "lat", "lon", "elevation_m",
            "restaurant_type", "ski_area_hint", "osm_id", "osm_type",
            "website", "lunch_main_eur", "lunch_drink_eur", "price_source",
            "is_estimate", "menu_url", "price_source_detail", "price_level",
            "confidence", "reason_price",
        }
        assert set(row.keys()) == expected_keys

    def test_copies_osm_fields(self):
        rec = {"name": "Test", "country": "CH", "region": "Wallis",
               "lat": 46.0, "lon": 7.5, "osm_id": 42, "osm_type": "node"}
        row = _restaurant_row(rec)
        assert row["osm_id"] == 42
        assert row["osm_type"] == "node"


# ---------------------------------------------------------------------------
# mock run (integration)
# ---------------------------------------------------------------------------

class TestMockRun:
    def test_mock_run_writes_csv(self, tmp_path):
        cfg = yaml.safe_load(
            (Path(__file__).resolve().parents[3] / "config.yaml").read_text()
        )
        cfg["llm"]["provider"] = "mock"
        cfg["data_dir"] = str(tmp_path / "data")

        run(cfg, limit_batches=1)

        csv_path = tmp_path / "data" / "processed" / "restaurants.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) == 8
        assert set(df["country"].unique()) == {"CH", "AT", "DE", "IT", "FR"}
        assert df["lunch_main_eur"].notna().all()
        assert (df["is_estimate"] == True).all()
        assert (df["price_source"] == "country_statistics_estimate").all()

    def test_restaurant_id_format(self, tmp_path):
        cfg = yaml.safe_load(
            (Path(__file__).resolve().parents[3] / "config.yaml").read_text()
        )
        cfg["llm"]["provider"] = "mock"
        cfg["data_dir"] = str(tmp_path / "data")

        run(cfg, limit_batches=1)

        df = pd.read_csv(tmp_path / "data" / "processed" / "restaurants.csv")
        for rid in df["restaurant_id"]:
            parts = rid.split("-")
            assert len(parts) >= 3
            assert parts[0].isalpha() and len(parts[0]) == 2


# ---------------------------------------------------------------------------
# Architecture constraint
# ---------------------------------------------------------------------------

def test_no_resort_data_dependency():
    """C2 must not import from resort_source."""
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
