"""Tests for C1 resort_source against example data with mock provider."""

import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def mock_cfg(project_root, tmp_path):
    """Load config.yaml and override for mock testing."""
    cfg_path = project_root / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["llm"]["provider"] = "mock"
    cfg["data_dir"] = str(tmp_path / "data")
    cfg["log_dir"] = str(tmp_path / "logs")
    cfg["resorts"]["min_items"] = 1

    (tmp_path / "data" / "raw" / "resort_source").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)

    return cfg


def test_fetch_resort_list_returns_resorts(mock_cfg):
    """fetch_resort_list should return a non-empty list with mock provider."""
    from components.resort_source.core import fetch_resort_list

    resorts, merge_log = fetch_resort_list(mock_cfg, limit_batches=1)
    assert len(resorts) > 0
    for r in resorts:
        assert "resort_id" in r
        assert "name" in r
        assert "country" in r


def test_size_class():
    from components.resort_source.core import _size_class

    assert _size_class(10) == "small"
    assert _size_class(50) == "medium"
    assert _size_class(150) == "large"
    assert _size_class(None) == "small"
    assert _size_class(30) == "medium"
    assert _size_class(100) == "medium"
