"""Tests for C7 validator against example data."""

import pandas as pd
import pytest

from components.validator.core import (
    check_fact_accuracy,
    check_item_rules,
    generate_sample,
)


@pytest.fixture
def sample_resorts():
    return pd.DataFrame([
        {
            "resort_id": "ch-flumserberg", "name": "Flumserberg",
            "country": "CH", "region": "Ostschweiz",
            "lat": 47.0833, "lon": 9.2833,
            "top_elevation_m": 2222, "base_elevation_m": 600,
            "slope_km": 65, "size_class": "medium",
            "day_pass_adult_eur": 58.0, "day_pass_youth16_eur": 46.0,
            "day_pass_child13_eur": 29.0, "family_pass_eur": 170.0,
            "drive_time_min": 120, "drive_distance_km": 150,
            "snow_reliability": 6, "family_friendliness": 8,
            "value_for_money": 7, "confidence": "medium",
            "n_runs_valid": 3, "value_rank": 1,
        },
        {
            "resort_id": "de-fellhorn", "name": "Fellhorn/Kanzelwand",
            "country": "DE", "region": "Bayern",
            "lat": 47.35, "lon": 10.2333,
            "top_elevation_m": 2037, "base_elevation_m": 920,
            "slope_km": 36, "size_class": "small",
            "day_pass_adult_eur": 52.0, "day_pass_youth16_eur": 42.0,
            "day_pass_child13_eur": 26.0, "family_pass_eur": None,
            "drive_time_min": 130, "drive_distance_km": 180,
            "snow_reliability": 5, "family_friendliness": 7,
            "value_for_money": 6, "confidence": "low",
            "n_runs_valid": 3, "value_rank": 3,
        },
    ])


def test_generate_sample_produces_rows(sample_resorts):
    cfg = {"acceptance": {"fact_check_tolerance": 0.2}}
    sample = generate_sample(sample_resorts, None, None, cfg)
    assert len(sample) > 0
    assert "item_type" in sample.columns
    assert (sample["item_type"] == "resort").all()
    assert sample["target_value"].isna().all()


def test_check_fact_accuracy_all_correct():
    df = pd.DataFrame([
        {"item_type": "resort", "item_id": "x", "attribute": "slope_km",
         "llm_value": "100", "target_value": "95"},
    ])
    acc, flags = check_fact_accuracy(df, tolerance=0.20)
    assert acc == 1.0
    assert len(flags) == 0


def test_check_fact_accuracy_deviation():
    df = pd.DataFrame([
        {"item_type": "resort", "item_id": "x", "attribute": "slope_km",
         "llm_value": "100", "target_value": "50"},
    ])
    acc, flags = check_fact_accuracy(df, tolerance=0.20)
    assert acc == 0.0
    assert len(flags) == 1
    assert flags[0]["severity"] == "error"


def test_check_item_rules_base_above_top():
    df = pd.DataFrame([{
        "resort_id": "bad-resort",
        "base_elevation_m": 3000, "top_elevation_m": 2000,
        "lat": 47.0, "lon": 10.0, "slope_km": 50, "size_class": "medium",
    }])
    flags = check_item_rules(df)
    assert any(f["check_id"] == "elevation_order" for f in flags)


def test_check_item_rules_coords_outside_alps():
    df = pd.DataFrame([{
        "resort_id": "weird",
        "base_elevation_m": 500, "top_elevation_m": 2000,
        "lat": 30.0, "lon": 10.0, "slope_km": 50, "size_class": "medium",
    }])
    flags = check_item_rules(df)
    assert any(f["check_id"] == "coords_in_alps" for f in flags)


def test_check_item_rules_size_class_mismatch():
    df = pd.DataFrame([{
        "resort_id": "misclassed",
        "base_elevation_m": 500, "top_elevation_m": 2000,
        "lat": 47.0, "lon": 10.0, "slope_km": 150, "size_class": "small",
    }])
    flags = check_item_rules(df)
    assert any(f["check_id"] == "size_class_match" for f in flags)
