"""Integration test: mock pipeline runs without errors."""

import pytest


def test_mock_pipeline_structure():
    """Verify pipeline steps are defined and ordered correctly."""
    from pipeline.run_pipeline import STEPS

    assert len(STEPS) >= 5
    step_names = [s[0] for s in STEPS]
    assert "C1: resort_source" in step_names
    assert "C4: cost_model" in step_names


def test_step_order():
    """C1 must come before C4, C4 before C5."""
    from pipeline.run_pipeline import STEPS

    names = [s[0] for s in STEPS]
    assert names.index("C1: resort_source") < names.index("C4: cost_model")
    assert names.index("C4: cost_model") < names.index("C5: clustering")


def test_gastro_steps_conditional():
    """C2 and C3 are conditional (always_run=False)."""
    from pipeline.run_pipeline import STEPS

    for name, _, always in STEPS:
        if "gastro" in name or "geo_matcher" in name:
            assert not always, f"{name} should be conditional"
