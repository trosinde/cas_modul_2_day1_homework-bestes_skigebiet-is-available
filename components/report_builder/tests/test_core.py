"""Tests for C8 report_builder."""

import tempfile
from pathlib import Path

from components.report_builder.core import read_task_text, build_report_md


def test_read_task_text_existing():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.md"
        p.write_text("Hello world", encoding="utf-8")
        assert read_task_text(d, "test.md") == "Hello world"


def test_read_task_text_missing():
    result = read_task_text("/nonexistent", "missing.md")
    assert "noch nicht geschrieben" in result


def test_build_report_md_contains_sections():
    cfg = {}
    md = build_report_md(cfg)
    assert "# Task 1" in md
    assert "# Task 2" in md
    assert "# Task 6" in md
    assert "github.com/trosinde" in md
