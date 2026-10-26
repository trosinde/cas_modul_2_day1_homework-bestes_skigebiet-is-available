"""Tests for C3 geo_matcher against example data with known distances."""

import pandas as pd
import pytest
from pathlib import Path

from components.geo_matcher.core import match_restaurants, compute_resort_lunch

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"

MATCHING_CFG = {
    "matching": {
        "radius_km": {"small": 5, "medium": 8, "large": 15},
        "ambiguity_km": 1.0,
        "min_restaurants": 1,
    }
}


@pytest.fixture
def resorts_df():
    path = EXAMPLES / "resorts.csv"
    if not path.exists():
        pytest.skip("Example resorts.csv not yet created")
    return pd.read_csv(path)


@pytest.fixture
def restaurants_df():
    path = EXAMPLES / "restaurants.csv"
    if not path.exists():
        pytest.skip("Example restaurants.csv not yet created")
    return pd.read_csv(path)


def test_match_counts(resorts_df, restaurants_df):
    """The example data should produce 6 matched, 2 ambiguous, 2 unmatched."""
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)

    assert len(matches) == len(restaurants_df), "One match row per restaurant"

    status_counts = matches["match_status"].value_counts().to_dict()
    assert status_counts.get("matched", 0) == 6, \
        f"Expected 6 matched, got {status_counts}"
    assert status_counts.get("ambiguous", 0) == 2, \
        f"Expected 2 ambiguous, got {status_counts}"
    assert status_counts.get("unmatched", 0) == 2, \
        f"Expected 2 unmatched, got {status_counts}"


def test_every_restaurant_appears_once(resorts_df, restaurants_df):
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)
    assert matches["restaurant_id"].is_unique


def test_unmatched_have_null_resort(resorts_df, restaurants_df):
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)
    unmatched = matches[matches["match_status"] == "unmatched"]
    assert unmatched["resort_id"].isna().all()


def test_matched_have_resort(resorts_df, restaurants_df):
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)
    matched = matches[matches["match_status"].isin(["matched", "ambiguous"])]
    assert matched["resort_id"].notna().all()


def test_resort_lunch_one_row_per_resort(resorts_df, restaurants_df):
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)
    lunch = compute_resort_lunch(matches, restaurants_df, resorts_df, MATCHING_CFG)
    assert len(lunch) == len(resorts_df)
    assert lunch["resort_id"].is_unique


def test_resort_lunch_prices_positive(resorts_df, restaurants_df):
    matches = match_restaurants(resorts_df, restaurants_df, MATCHING_CFG)
    lunch = compute_resort_lunch(matches, restaurants_df, resorts_df, MATCHING_CFG)
    assert (lunch["lunch_main_eur"] > 0).all()
    assert (lunch["lunch_drink_eur"] > 0).all()
