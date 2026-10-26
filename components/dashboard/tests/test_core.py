"""Tests for C6 dashboard core logic."""

import math
import numpy as np
from components.dashboard.core import clean_for_json


def test_clean_for_json_nan():
    assert clean_for_json(float("nan")) is None


def test_clean_for_json_inf():
    assert clean_for_json(float("inf")) is None


def test_clean_for_json_nested():
    data = {"a": [1, float("nan"), {"b": np.int64(42), "c": np.float64(3.14), "d": np.bool_(True)}]}
    result = clean_for_json(data)
    assert result["a"][1] is None
    assert result["a"][2]["b"] == 42
    assert isinstance(result["a"][2]["b"], int)
    assert isinstance(result["a"][2]["c"], float)
    assert result["a"][2]["d"] is True


def test_clean_for_json_passthrough():
    assert clean_for_json("hello") == "hello"
    assert clean_for_json(42) == 42
    assert clean_for_json(None) is None
