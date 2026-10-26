"""LLM Gateway – single point of access to language models."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        """Fallback: load .env manually if python-dotenv is not installed."""
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


@dataclass
class GatewayResult:
    ok: bool
    records: list[dict] = field(default_factory=list)
    raw_path: Path | None = None
    attempts: int = 0
    error: str | None = None


def _load_prompt(template_id: str, variables: dict, prompts_dir: str = "prompts") -> str:
    path = Path(prompts_dir) / f"{template_id}.md"
    template = path.read_text(encoding="utf-8")
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


def _load_system_prompt(prompts_dir: str = "prompts") -> str:
    path = Path(prompts_dir) / "system.md"
    return path.read_text(encoding="utf-8")


def _validate_records(records: list[dict], schema_id: str, contracts_dir: str = "contracts") -> list[dict]:
    schema_path = Path(contracts_dir) / f"{schema_id}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    valid = []
    for rec in records:
        try:
            jsonschema.validate(rec, schema)
            valid.append(rec)
        except jsonschema.ValidationError:
            pass
    return valid


def _save_envelope(
    out_path: Path,
    kind: str,
    template_id: str,
    provider: str,
    model: str,
    temperature: float,
    raw_response: str,
    records: list[dict],
    attempts: int,
    error: str | None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    envelope = {
        "kind": kind,
        "template_id": template_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "records": records,
        "raw_response": raw_response,
        "attempts": attempts,
        "error": error,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")


def _call_anthropic(system_prompt: str, user_prompt: str, model: str, temperature: float) -> tuple[str, int, int]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = response.content[0].text
    return text, response.usage.input_tokens, response.usage.output_tokens


def _call_openai(system_prompt: str, user_prompt: str, model: str, temperature: float) -> tuple[str, int, int]:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content
    usage = response.usage
    return text, usage.prompt_tokens, usage.completion_tokens


def _call_mock(template_id: str, variables: dict, mock_dir: str = "contracts/examples/llm_responses") -> tuple[str, int, int]:
    mock_path = Path(mock_dir)
    candidates = [f"{template_id}.json"]
    if "country" in variables:
        candidates.append(f"{template_id}_{variables['country'].lower()}.json")
    if "region" in variables:
        region_slug = (
            variables["region"]
            .lower()
            .replace(" ", "_")
            .replace("ü", "ue")
            .replace("ä", "ae")
            .replace("ö", "oe")
        )
        country = variables.get("country_code", variables.get("country", "")).lower()
        candidates.append(f"{template_id}_{country}_{region_slug}.json")
    if "batch_list" in variables:
        for i in range(1, 20):
            candidates.append(f"{template_id}_batch{i}.json")

    for candidate in candidates:
        path = mock_path / candidate
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return text, 100, 200

    for p in sorted(mock_path.glob(f"{template_id}*.json")):
        text = p.read_text(encoding="utf-8")
        return text, 100, 200

    raise FileNotFoundError(
        f"No mock response found for template_id={template_id} in {mock_dir}"
    )


def _detect_provider(cfg: dict) -> tuple[str, str]:
    load_dotenv()
    provider = cfg.get("llm", {}).get("provider", "auto")
    models = cfg.get("llm", {}).get("models", {})

    if provider == "mock":
        return "mock", "mock"

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if provider == "auto":
        if has_anthropic and has_openai:
            print(
                "ERROR: Both ANTHROPIC_API_KEY and OPENAI_API_KEY set with provider: auto.\n"
                "Set provider explicitly in config.yaml."
            )
            raise SystemExit(2)
        if has_anthropic:
            return "anthropic", models.get("anthropic", "claude-sonnet-4-20250514")
        if has_openai:
            return "openai", models.get("openai", "gpt-4o")
        print("ERROR: No API key found in .env. Set provider: mock for development.")
        raise SystemExit(2)

    if provider == "anthropic":
        if not has_anthropic:
            print("ERROR: provider: anthropic but ANTHROPIC_API_KEY not set in .env")
            raise SystemExit(2)
        return "anthropic", models.get("anthropic", "claude-sonnet-4-20250514")

    if provider == "openai":
        if not has_openai:
            print("ERROR: provider: openai but OPENAI_API_KEY not set in .env")
            raise SystemExit(2)
        return "openai", models.get("openai", "gpt-4o")

    raise SystemExit(2)


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        text = "\n".join(json_lines)
    return json.loads(text)


def generate_json(
    template_id: str,
    variables: dict,
    record_schema_id: str,
    temperature: float,
    out_path: Path,
    cfg: dict,
    kind: str = "resort_items",
    prompts_dir: str = "prompts",
    contracts_dir: str = "contracts",
) -> GatewayResult:
    """Generate structured JSON from LLM, validate records, save envelope."""
    provider, model = _detect_provider(cfg)
    max_retries = cfg.get("llm", {}).get("max_retries", 3)

    system_prompt = _load_system_prompt(prompts_dir)
    user_prompt = _load_prompt(template_id, variables, prompts_dir)

    raw_text = ""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            if provider == "mock":
                raw_text, p_tokens, c_tokens = _call_mock(
                    template_id, variables
                )
            elif provider == "anthropic":
                raw_text, p_tokens, c_tokens = _call_anthropic(
                    system_prompt, user_prompt, model, temperature
                )
            elif provider == "openai":
                raw_text, p_tokens, c_tokens = _call_openai(
                    system_prompt, user_prompt, model, temperature
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")

            data = _extract_json(raw_text)

            records = []
            for key in ("resorts", "restaurants"):
                if key in data:
                    records = data[key]
                    break
            if not records and isinstance(data, list):
                records = data

            valid_records = _validate_records(records, record_schema_id, contracts_dir)

            _save_envelope(
                out_path, kind, template_id, provider, model, temperature,
                raw_text, valid_records, attempt, None, p_tokens, c_tokens,
            )

            return GatewayResult(
                ok=True, records=valid_records, raw_path=out_path, attempts=attempt
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = str(e)
            _save_envelope(
                out_path, kind, template_id, provider, model, temperature,
                raw_text, [], attempt, last_error,
            )
            continue
        except Exception as e:
            last_error = str(e)
            _save_envelope(
                out_path, kind, template_id, provider, model, temperature,
                raw_text, [], attempt, last_error,
            )
            if attempt == max_retries:
                break

    return GatewayResult(ok=False, attempts=max_retries, error=last_error)
