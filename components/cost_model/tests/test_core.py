"""Tests for C4 cost_model against example data."""

import math

import numpy as np
import pandas as pd
import pytest

from components.cost_model.core import compute_costs

EXAMPLE_CFG = {
    "costs": {
        "cost_per_km": 0.30,
        "max_drive_time_min": 180,
        "default_variant": "v2",
    },
    "quality": {
        "weights": {
            "snow_reliability": 0.40,
            "family_friendliness": 0.35,
            "size_norm": 0.25,
        },
    },
    "include_lunch_cost": False,
}


def _make_resorts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "resort_id": "ch-flumserberg",
                "name": "Flumserberg",
                "country": "CH",
                "day_pass_adult_eur": 57.0,
                "day_pass_youth16_eur": 38.0,
                "day_pass_child13_eur": 28.5,
                "family_pass_eur": 160.0,
                "drive_distance_km": 130.0,
                "drive_time_min": 100,
                "slope_km": 65.0,
                "snow_reliability": 6,
                "family_friendliness": 7,
                "n_runs_valid": 3,
            },
            {
                "resort_id": "at-schladming",
                "name": "Schladming-Dachstein",
                "country": "AT",
                "day_pass_adult_eur": 62.0,
                "day_pass_youth16_eur": 46.5,
                "day_pass_child13_eur": 31.0,
                "family_pass_eur": np.nan,
                "drive_distance_km": 380.0,
                "drive_time_min": 240,
                "slope_km": 123.0,
                "snow_reliability": 8,
                "family_friendliness": 7,
                "n_runs_valid": 3,
            },
            {
                "resort_id": "de-fellhorn",
                "name": "Fellhorn/Kanzelwand",
                "country": "DE",
                "day_pass_adult_eur": 52.0,
                "day_pass_youth16_eur": 39.0,
                "day_pass_child13_eur": 26.0,
                "family_pass_eur": 150.0,
                "drive_distance_km": 160.0,
                "drive_time_min": 120,
                "slope_km": 36.0,
                "snow_reliability": 5,
                "family_friendliness": 8,
                "n_runs_valid": 3,
            },
        ]
    )


def test_family_pass_used():
    df = _make_resorts()
    result = compute_costs(df, None, EXAMPLE_CFG)

    # Flumserberg: individual = 2*57+38+28.5 = 180.5 > 160 → family pass used
    row_fl = result[result["resort_id"] == "ch-flumserberg"].iloc[0]
    assert row_fl["family_pass_used"] is True or row_fl["family_pass_used"] == True
    assert row_fl["family_pass_cost_eur"] == 160.0

    # Schladming: no family pass → individual
    row_sc = result[result["resort_id"] == "at-schladming"].iloc[0]
    assert row_sc["family_pass_used"] is False or row_sc["family_pass_used"] == False
    expected_individual = 2 * 62.0 + 46.5 + 31.0
    assert row_sc["family_pass_cost_eur"] == expected_individual


def test_travel_cost():
    df = _make_resorts()
    result = compute_costs(df, None, EXAMPLE_CFG)
    row = result[result["resort_id"] == "ch-flumserberg"].iloc[0]
    expected = 2 * 130.0 * 0.30
    assert abs(row["travel_cost_eur"] - expected) < 0.01


def test_day_cost_variants():
    df = _make_resorts()
    result = compute_costs(df, None, EXAMPLE_CFG)
    row = result[result["resort_id"] == "ch-flumserberg"].iloc[0]
    assert row["day_cost_v1_eur"] == row["family_pass_cost_eur"]
    assert abs(row["day_cost_v2_eur"] - (row["day_cost_v1_eur"] + row["travel_cost_eur"])) < 0.01
    assert pd.isna(row["day_cost_v3_eur"]) or row["day_cost_v3_eur"] is None


def test_quality_score():
    df = _make_resorts()
    result = compute_costs(df, None, EXAMPLE_CFG)
    row = result[result["resort_id"] == "ch-flumserberg"].iloc[0]
    max_slope = df["slope_km"].max()
    size_norm = math.log(65) / math.log(max_slope)
    expected = round(0.40 * 6 + 0.35 * 7 + 0.25 * size_norm * 10, 2)
    assert abs(row["quality_score"] - expected) < 0.02


def test_ranking_excludes_long_drive():
    df = _make_resorts()
    result = compute_costs(df, None, EXAMPLE_CFG)
    # Schladming: 240 min > 180 → not in ranking
    row = result[result["resort_id"] == "at-schladming"].iloc[0]
    assert row["in_ranking"] == False
    assert pd.isna(row["value_rank"])


def test_with_lunch():
    df = _make_resorts()
    lunch = pd.DataFrame(
        [
            {"resort_id": "ch-flumserberg", "lunch_main_eur": 18.0, "lunch_drink_eur": 4.5, "lunch_source": "matched"},
            {"resort_id": "at-schladming", "lunch_main_eur": 16.0, "lunch_drink_eur": 4.0, "lunch_source": "matched"},
            {"resort_id": "de-fellhorn", "lunch_main_eur": 15.0, "lunch_drink_eur": 4.0, "lunch_source": "country_median"},
        ]
    )
    cfg = {**EXAMPLE_CFG, "include_lunch_cost": True}
    result = compute_costs(df, lunch, cfg)

    row = result[result["resort_id"] == "ch-flumserberg"].iloc[0]
    expected_lunch = 4 * (18.0 + 4.5)
    assert abs(row["lunch_cost_eur"] - expected_lunch) < 0.01
    assert row["day_cost_v3_eur"] == row["day_cost_v2_eur"] + row["lunch_cost_eur"]
    assert row["family_day_cost_eur"] == row["day_cost_v3_eur"]
