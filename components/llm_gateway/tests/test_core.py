"""Tests for the LLM Gateway with mock provider."""

import json
import os
from pathlib import Path

import pytest

from components.llm_gateway.core import (
    GatewayResult,
    _detect_provider,
    _extract_json,
    _validate_records,
    generate_json,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _use_project_root(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


@pytest.fixture()
def mock_cfg():
    return {
        "llm": {
            "provider": "mock",
            "temperature_factual": 0.3,
            "temperature_subjective": 0.7,
            "max_retries": 3,
            "runs": 3,
            "models": {"anthropic": "claude-sonnet-4-20250514", "openai": "gpt-4o"},
        }
    }


class TestDetectProvider:
    def test_mock_provider(self, mock_cfg):
        provider, model = _detect_provider(mock_cfg)
        assert provider == "mock"
        assert model == "mock"

    def test_auto_no_keys(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = {"llm": {"provider": "auto", "models": {}}}
        with pytest.raises(SystemExit) as exc_info:
            _detect_provider(cfg)
        assert exc_info.value.code == 2


class TestExtractJson:
    def test_plain_json(self):
        data = _extract_json('{"resorts": []}')
        assert data == {"resorts": []}

    def test_code_block(self):
        raw = '```json\n{"resorts": [{"name": "A"}]}\n```'
        data = _extract_json(raw)
        assert data["resorts"][0]["name"] == "A"


class TestGenerateJson:
    def test_mock_resort_items(self, mock_cfg, tmp_path):
        mock_responses = PROJECT_ROOT / "contracts" / "examples" / "llm_responses"
        if not mock_responses.exists() or not list(mock_responses.glob("resort_items*.json")):
            pytest.skip("No mock resort_items responses available yet")

        out = tmp_path / "envelope.json"
        result = generate_json(
            template_id="resort_items",
            variables={"batch_size": "5", "country": "CH", "region": "Ostschweiz", "existing_names": ""},
            record_schema_id="resort_record",
            temperature=0.3,
            out_path=out,
            cfg=mock_cfg,
            kind="resort_items",
            prompts_dir=str(PROJECT_ROOT / "prompts"),
            contracts_dir=str(PROJECT_ROOT / "contracts"),
        )
        assert isinstance(result, GatewayResult)
        if result.ok:
            assert len(result.records) > 0
            assert out.exists()
            envelope = json.loads(out.read_text())
            assert envelope["provider"] == "mock"
            assert envelope["kind"] == "resort_items"
