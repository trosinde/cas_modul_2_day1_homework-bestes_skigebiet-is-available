"""Tests for C1 resort_source against example data with mock provider."""

import json
import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def mock_cfg(project_root, tmp_path):
    """Load config.yaml and override for mock testing with cached data."""
    cfg_path = project_root / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["llm"]["provider"] = "mock"
    cfg["data_dir"] = str(tmp_path / "data")
    cfg["log_dir"] = str(tmp_path / "logs")
    cfg["report_dir"] = str(tmp_path / "report")
    cfg["resorts"]["min_items"] = 1

    raw = tmp_path / "data" / "raw" / "resort_source"
    raw.mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "report" / "figures").mkdir(parents=True)

    src_raw = project_root / "data" / "raw" / "resort_source"
    for subdir in ["osm", "osrm", "scraper", "openskidata"]:
        src = src_raw / subdir
        if src.exists():
            shutil.copytree(src, raw / subdir)

    return cfg


def test_osm_fetch_uses_cache(mock_cfg):
    """OSM fetch should use cached data and return resorts."""
    from components.resort_source.osm import fetch_osm_resorts

    resorts = fetch_osm_resorts(mock_cfg)
    assert len(resorts) > 0
    for r in resorts:
        assert "resort_id" in r
        assert "name" in r
        assert "country" in r
        assert "lat" in r
        assert "lon" in r
        assert r["lat"] >= 43 and r["lat"] <= 49


def test_routing_uses_cache(mock_cfg):
    """OSRM routing should use cached data."""
    from components.resort_source.routing import fetch_routes
    from components.resort_source.osm import fetch_osm_resorts

    resorts = fetch_osm_resorts(mock_cfg)
    routes = fetch_routes(resorts, mock_cfg)
    assert len(routes) > 0
    for rid, route in routes.items():
        assert "drive_distance_km" in route
        assert "drive_time_min" in route


def test_size_class():
    from components.resort_source.core import _size_class

    assert _size_class(10) == "small"
    assert _size_class(50) == "medium"
    assert _size_class(150) == "large"
    assert _size_class(None) == "small"
    assert _size_class(30) == "medium"
    assert _size_class(100) == "medium"


def test_full_pipeline_mock(mock_cfg):
    """Full C1 pipeline should complete with mock data."""
    from components.resort_source.core import run

    run(mock_cfg, limit_batches=1)

    processed = Path(mock_cfg["data_dir"]) / "processed"
    resorts_csv = processed / "resorts.csv"
    assert resorts_csv.exists()

    import pandas as pd
    df = pd.read_csv(resorts_csv)
    assert len(df) > 0
    assert "source_coords" in df.columns
    assert "source_driving" in df.columns
    assert "source_prices" in df.columns
    assert "source_ratings" in df.columns
    assert all(df["source_coords"] == "openskidata")
    assert all(df["source_driving"] == "osrm")
    assert all(df["source_ratings"] == "llm")
