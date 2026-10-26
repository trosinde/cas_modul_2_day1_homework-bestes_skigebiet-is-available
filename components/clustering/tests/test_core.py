"""Tests for C5 clustering against example data."""

import pandas as pd
import numpy as np
import pytest

from components.clustering.core import find_best_k, run_clustering


@pytest.fixture
def example_costs():
    """Minimal cost data matching the 5 example resorts."""
    return pd.DataFrame([
        {
            "resort_id": "ch-flumserberg",
            "quality_score": 6.50, "family_day_cost_eur": 320.0,
            "slope_km": 65, "snow_reliability": 6, "family_friendliness": 7,
            "drive_time_min": 120, "n_runs_valid": 3,
        },
        {
            "resort_id": "at-schladming-dachstein",
            "quality_score": 7.80, "family_day_cost_eur": 480.0,
            "slope_km": 123, "snow_reliability": 8, "family_friendliness": 7,
            "drive_time_min": 240, "n_runs_valid": 3,
        },
        {
            "resort_id": "de-fellhorn-kanzelwand",
            "quality_score": 5.20, "family_day_cost_eur": 260.0,
            "slope_km": 36, "snow_reliability": 5, "family_friendliness": 6,
            "drive_time_min": 120, "n_runs_valid": 3,
        },
        {
            "resort_id": "it-kronplatz",
            "quality_score": 7.50, "family_day_cost_eur": 420.0,
            "slope_km": 119, "snow_reliability": 7, "family_friendliness": 8,
            "drive_time_min": 210, "n_runs_valid": 3,
        },
        {
            "resort_id": "ch-arosa-lenzerheide",
            "quality_score": 8.10, "family_day_cost_eur": 450.0,
            "slope_km": 225, "snow_reliability": 8, "family_friendliness": 8,
            "drive_time_min": 150, "n_runs_valid": 3,
        },
    ])


@pytest.fixture
def example_cfg():
    return {
        "clustering": {
            "k_min": 2,
            "k_max": 4,
            "random_state": 42,
            "features": [
                "quality_score", "family_day_cost_eur", "slope_km",
                "snow_reliability", "family_friendliness", "drive_time_min",
            ],
        },
    }


def test_find_best_k():
    rng = np.random.RandomState(42)
    X = np.vstack([rng.randn(10, 2) + [0, 0], rng.randn(10, 2) + [5, 5]])
    best_k, scores = find_best_k(X, 2, 4, random_state=42)
    assert best_k == 2
    assert all(0 < s <= 1 for s in scores.values())


def test_run_clustering_shape(example_costs, example_cfg):
    result, meta = run_clustering(example_costs, example_cfg)
    assert len(result) == 5
    assert set(result.columns) == {"resort_id", "cluster_id", "cluster_label", "pc1", "pc2", "silhouette"}
    assert result["cluster_id"].between(0, 10).all()
    assert result["silhouette"].between(-1, 1).all()
    assert meta["best_k"] >= 2


def test_cluster_labels_filled(example_costs, example_cfg):
    result, _ = run_clustering(example_costs, example_cfg)
    assert result["cluster_label"].notna().all()
    assert (result["cluster_label"] != "").all()
