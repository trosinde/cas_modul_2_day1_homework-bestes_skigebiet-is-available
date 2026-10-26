"""C1 resort_source – fetch ski resort data via LLM in two phases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from common.config import load as load_config
from common.ids import resort_id, slugify
from common.log import get_logger
from common.paths import raw_dir, processed_dir
from common.runs import merge_resort_runs
from components.llm_gateway import generate_json

logger = get_logger("resort_source")

NUMERIC_ATTRS = [
    "top_elevation_m", "base_elevation_m", "slope_km",
    "day_pass_adult_eur", "day_pass_youth16_eur", "day_pass_child13_eur",
    "family_pass_eur", "drive_time_min", "drive_distance_km",
    "snow_reliability", "family_friendliness", "value_for_money",
]

CATEGORICAL_ATTRS = ["size_class", "confidence"]

TEXT_ATTRS = [
    "age_category_16", "age_category_13",
    "family_pass_conditions",
    "reason_snow", "reason_family", "reason_value",
]


def _normalise_name(name: str) -> str:
    return slugify(name).lower()


def _size_class(slope_km: float | None) -> str:
    if slope_km is None:
        return "small"
    if slope_km < 30:
        return "small"
    if slope_km <= 100:
        return "medium"
    return "large"


def fetch_resort_list(
    cfg: dict,
    limit_batches: int | None = None,
) -> list[dict]:
    """Phase 1: get flat list of resort names per country."""
    countries = cfg["resorts"]["countries"]
    batch_size = cfg["resorts"]["batch_size"]
    raw = raw_dir(cfg, "resort_source")
    seen_normalised: set[str] = set()
    resorts: list[dict] = []
    merge_log: list[dict] = []

    for country in countries:
        batch_idx = 0
        existing_names: list[str] = [r["name"] for r in resorts if r["country"] == country]

        while True:
            if limit_batches is not None and batch_idx >= limit_batches:
                break

            out_path = raw / "resort_items" / f"{country.lower()}_batch{batch_idx}.json"
            if out_path.exists():
                logger.info("Resuming: %s already exists, skipping", out_path)
                envelope = json.loads(out_path.read_text("utf-8"))
                records = envelope.get("records", [])
            else:
                result = generate_json(
                    template_id="resort_items",
                    variables={
                        "batch_size": batch_size,
                        "country": country,
                        "region": country,
                        "existing_names": ", ".join(existing_names) or "none",
                    },
                    record_schema_id="resort_record",
                    temperature=cfg["llm"]["temperature_factual"],
                    out_path=out_path,
                    cfg=cfg,
                    kind="resort_items",
                )
                if not result.ok:
                    logger.warning("LLM call failed for %s batch %d: %s", country, batch_idx, result.error)
                    break
                records = result.records

            if not records:
                break

            for rec in records:
                norm = _normalise_name(rec.get("name", ""))
                if norm in seen_normalised:
                    merge_log.append({
                        "batch_id": f"{country.lower()}_batch{batch_idx}",
                        "item_id": None,
                        "record_name": rec.get("name", ""),
                        "reason": "duplicate",
                        "detail": f"Normalised name '{norm}' already seen",
                    })
                    continue
                seen_normalised.add(norm)
                rid = resort_id(rec.get("country", country), rec["name"])
                resorts.append({
                    "resort_id": rid,
                    "name": rec["name"],
                    "country": rec.get("country", country),
                    "region": rec.get("region", ""),
                })
                existing_names.append(rec["name"])

            batch_idx += 1
            if len(records) < batch_size:
                break

    logger.info("Resort list: %d resorts from %d countries", len(resorts), len(countries))
    return resorts, merge_log


def fetch_resort_attributes(
    resort_list: list[dict],
    cfg: dict,
    run_num: int,
    limit_batches: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Phase 2: fetch attributes for all resorts in one run."""
    batch_size = cfg["resorts"]["batch_size"]
    raw = raw_dir(cfg, "resort_source")
    records: list[dict] = []
    merge_log: list[dict] = []

    batches = [
        resort_list[i : i + batch_size]
        for i in range(0, len(resort_list), batch_size)
    ]

    for batch_idx, batch in enumerate(batches):
        if limit_batches is not None and batch_idx >= limit_batches:
            break

        out_path = raw / f"resort_attributes_run{run_num}" / f"batch{batch_idx}.json"
        if out_path.exists():
            logger.info("Resuming: %s already exists, skipping", out_path)
            envelope = json.loads(out_path.read_text("utf-8"))
            batch_records = envelope.get("records", [])
        else:
            batch_list_str = "\n".join(
                f"- {r['resort_id']}: {r['name']} ({r['country']}, {r['region']})"
                for r in batch
            )
            result = generate_json(
                template_id="resort_attributes",
                variables={
                    "batch_list": batch_list_str,
                    "chf_to_eur": cfg["costs"]["chf_to_eur"],
                },
                record_schema_id="resort_record",
                temperature=cfg["llm"]["temperature_factual"],
                out_path=out_path,
                cfg=cfg,
                kind="resort_attributes",
            )
            if not result.ok:
                logger.warning("Attributes failed run %d batch %d: %s", run_num, batch_idx, result.error)
                continue
            batch_records = result.records

        expected_ids = {r["resort_id"] for r in batch}
        for rec in batch_records:
            rid = rec.get("resort_id")
            if rid and rid not in expected_ids:
                merge_log.append({
                    "batch_id": f"run{run_num}_batch{batch_idx}",
                    "item_id": rid,
                    "record_name": rec.get("name", rid),
                    "reason": "unknown_item",
                    "detail": f"resort_id '{rid}' not in batch",
                })
                continue

            if rec.get("lat") is None or rec.get("lon") is None:
                merge_log.append({
                    "batch_id": f"run{run_num}_batch{batch_idx}",
                    "item_id": rid,
                    "record_name": rec.get("name", ""),
                    "reason": "schema_violation",
                    "detail": "Missing lat/lon",
                })
                continue

            rec["run"] = run_num
            rec["size_class"] = _size_class(rec.get("slope_km"))
            records.append(rec)

    logger.info("Run %d: %d valid attribute records", run_num, len(records))
    return records, merge_log


def _build_runs_df(all_run_records: list[dict]) -> pd.DataFrame:
    """Build resorts_runs.csv DataFrame from all run records."""
    cols = ["resort_id", "run", "name", "country", "region", "lat", "lon"]
    cols += NUMERIC_ATTRS + CATEGORICAL_ATTRS + TEXT_ATTRS
    rows = []
    for rec in all_run_records:
        row = {c: rec.get(c) for c in cols}
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


def _build_merged_df(runs_df: pd.DataFrame) -> pd.DataFrame:
    """Merge 3 runs into final resorts.csv."""
    return merge_resort_runs(
        runs_df,
        numeric_attrs=NUMERIC_ATTRS,
        categorical_attrs=CATEGORICAL_ATTRS,
        text_attrs=TEXT_ATTRS,
    )


def run(
    cfg: dict,
    limit_batches: int | None = None,
    single_run: int | None = None,
) -> None:
    """Full C1 pipeline."""
    processed = processed_dir(cfg)
    processed.mkdir(parents=True, exist_ok=True)

    resort_list, list_merge_log = fetch_resort_list(cfg, limit_batches=limit_batches)

    if not resort_list:
        logger.error("No resorts found")
        raise SystemExit(3)

    runs_to_do = [single_run] if single_run else list(range(1, cfg["llm"]["runs"] + 1))
    all_run_records: list[dict] = []
    all_merge_log: list[dict] = list(list_merge_log)

    for run_num in runs_to_do:
        records, merge_log = fetch_resort_attributes(
            resort_list, cfg, run_num, limit_batches=limit_batches
        )
        all_run_records.extend(records)
        all_merge_log.extend(merge_log)

    runs_df = _build_runs_df(all_run_records)

    if runs_df.empty:
        logger.error("No valid attribute records from any run")
        raise SystemExit(3)

    runs_path = processed / "resorts_runs.csv"
    runs_df.to_csv(runs_path, index=False, encoding="utf-8")
    logger.info("Wrote %s (%d rows)", runs_path, len(runs_df))

    merged_df = _build_merged_df(runs_df)
    resorts_path = processed / "resorts.csv"
    merged_df.to_csv(resorts_path, index=False, encoding="utf-8")
    logger.info("Wrote %s (%d rows)", resorts_path, len(merged_df))

    if all_merge_log:
        log_df = pd.DataFrame(all_merge_log)
        log_path = processed / "resorts_merge_log.csv"
        log_df.to_csv(log_path, index=False, encoding="utf-8")
        logger.info("Wrote %s (%d entries)", log_path, len(log_df))

    min_items = cfg["resorts"]["min_items"]
    if len(merged_df) < min_items:
        logger.error(
            "Only %d resorts, need at least %d", len(merged_df), min_items
        )
        raise SystemExit(3)

    logger.info("C1 complete: %d resorts", len(merged_df))
