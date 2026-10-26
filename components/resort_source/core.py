"""C1 resort_source – fetch ski resort data via LLM in two phases."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

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

DUP_STOP_THRESHOLD = 0.5


class _Progress:
    """Thread-safe progress tracker with stderr status line."""

    def __init__(self, phase: str, total: int | None = None):
        self._lock = Lock()
        self._phase = phase
        self._total = total
        self._done = 0
        self._skipped = 0
        self._extra: dict[str, str] = {}
        self._start = time.monotonic()

    def tick(self, skipped: bool = False) -> None:
        with self._lock:
            self._done += 1
            if skipped:
                self._skipped += 1
            self._print()

    def set_total(self, total: int) -> None:
        with self._lock:
            self._total = total

    def set_extra(self, key: str, val: str) -> None:
        with self._lock:
            self._extra[key] = val
            self._print()

    def _print(self) -> None:
        elapsed = time.monotonic() - self._start
        parts = [f"\r  {self._phase}:"]
        if self._total and self._total > 0:
            pct = self._done / self._total * 100
            bar_w = 20
            filled = int(bar_w * self._done / self._total)
            bar = "█" * filled + "░" * (bar_w - filled)
            parts.append(f" {bar} {pct:5.1f}%  [{self._done}/{self._total}]")
        else:
            parts.append(f" {self._done} done")
        if self._skipped:
            parts.append(f"  ({self._skipped} cached)")
        if self._extra:
            parts.append("  " + " ".join(f"{k}={v}" for k, v in self._extra.items()))
        parts.append(f"  {elapsed:.0f}s")
        sys.stderr.write("".join(parts) + "   \r")
        sys.stderr.flush()

    def finish(self, msg: str = "") -> None:
        elapsed = time.monotonic() - self._start
        line = f"\r  {self._phase}: {msg}  ({elapsed:.1f}s)"
        sys.stderr.write(line + " " * 20 + "\n")
        sys.stderr.flush()


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


def _fetch_country_items(
    country: str,
    cfg: dict,
    limit_batches: int | None,
    seen_lock: Lock,
    seen_normalised: set[str],
    progress: _Progress | None = None,
) -> tuple[list[dict], list[dict]]:
    """Fetch resort items for one country. Thread-safe via seen_lock."""
    batch_size = cfg["resorts"]["batch_size"]
    raw = raw_dir(cfg, "resort_source")
    resorts: list[dict] = []
    merge_log: list[dict] = []
    existing_names: list[str] = []
    batch_idx = 0

    while True:
        if limit_batches is not None and batch_idx >= limit_batches:
            break

        out_path = raw / "resort_items" / f"{country.lower()}_batch{batch_idx}.json"
        was_cached = out_path.exists()
        if was_cached:
            logger.info("Resuming: %s exists, loading", out_path)
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
                record_schema_id="resort_item_record",
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

        new_in_batch = 0
        dup_in_batch = 0
        for rec in records:
            norm = _normalise_name(rec.get("name", ""))
            with seen_lock:
                is_dup = norm in seen_normalised
                if not is_dup:
                    seen_normalised.add(norm)

            if is_dup:
                dup_in_batch += 1
                merge_log.append({
                    "batch_id": f"{country.lower()}_batch{batch_idx}",
                    "item_id": None,
                    "record_name": rec.get("name", ""),
                    "reason": "duplicate",
                    "detail": f"Normalised name '{norm}' already seen",
                })
                continue
            new_in_batch += 1
            rid = resort_id(rec.get("country", country), rec["name"])
            resorts.append({
                "resort_id": rid,
                "name": rec["name"],
                "country": rec.get("country", country),
                "region": rec.get("region", ""),
            })
            existing_names.append(rec["name"])

        if progress:
            progress.tick(skipped=was_cached)
            progress.set_extra("resorts", str(len(resorts)))

        batch_idx += 1

        if len(records) < batch_size:
            break
        total_in_batch = new_in_batch + dup_in_batch
        if total_in_batch > 0 and dup_in_batch / total_in_batch >= DUP_STOP_THRESHOLD:
            logger.info(
                "%s: stopping after batch %d — %d/%d duplicates",
                country, batch_idx - 1, dup_in_batch, total_in_batch,
            )
            break

    logger.info("%s: %d resorts in %d batches", country, len(resorts), batch_idx)
    return resorts, merge_log


def fetch_resort_list(
    cfg: dict,
    limit_batches: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Phase 1: get resort names per country, countries fetched in parallel."""
    countries = cfg["resorts"]["countries"]
    seen_normalised: set[str] = set()
    seen_lock = Lock()
    progress = _Progress("Phase 1 — resort items")

    with ThreadPoolExecutor(max_workers=len(countries)) as pool:
        futures = {
            pool.submit(
                _fetch_country_items, country, cfg, limit_batches,
                seen_lock, seen_normalised, progress,
            ): country
            for country in countries
        }
        results_by_country: dict[str, tuple[list[dict], list[dict]]] = {}
        for future in as_completed(futures):
            country = futures[future]
            results_by_country[country] = future.result()

    resorts: list[dict] = []
    merge_log: list[dict] = []
    for country in countries:
        c_resorts, c_log = results_by_country[country]
        resorts.extend(c_resorts)
        merge_log.extend(c_log)

    progress.finish(f"{len(resorts)} resorts from {len(countries)} countries")
    logger.info("Resort list: %d resorts from %d countries", len(resorts), len(countries))
    return resorts, merge_log


def _fetch_attribute_batch(
    batch_idx: int,
    batch: list[dict],
    cfg: dict,
    run_num: int,
    raw: Path,
    progress: _Progress | None = None,
) -> tuple[list[dict], list[dict]]:
    """Fetch attributes for one batch. Skips if file already on disk."""
    records: list[dict] = []
    merge_log: list[dict] = []

    out_path = raw / f"resort_attributes_run{run_num}" / f"batch{batch_idx}.json"
    was_cached = out_path.exists()
    if was_cached:
        logger.info("Resuming: %s exists, loading", out_path)
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
            record_schema_id="resort_attribute_record",
            temperature=cfg["llm"]["temperature_factual"],
            out_path=out_path,
            cfg=cfg,
            kind="resort_attributes",
        )
        if not result.ok:
            logger.warning("Attributes failed run %d batch %d: %s", run_num, batch_idx, result.error)
            return records, merge_log
        batch_records = result.records

    id_to_info = {r["resort_id"]: r for r in batch}
    expected_ids = set(id_to_info.keys())
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

        if rid and rid in id_to_info:
            info = id_to_info[rid]
            rec.setdefault("name", info["name"])
            rec.setdefault("country", info["country"])
            rec.setdefault("region", info["region"])
        rec["run"] = run_num
        rec["size_class"] = _size_class(rec.get("slope_km"))
        records.append(rec)

    if progress:
        progress.tick(skipped=was_cached)

    return records, merge_log


def fetch_resort_attributes(
    resort_list: list[dict],
    cfg: dict,
    run_num: int,
    limit_batches: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Phase 2: fetch attributes for all resorts, batches in parallel."""
    batch_size = cfg["resorts"]["batch_size"]
    raw = raw_dir(cfg, "resort_source")

    batches = [
        resort_list[i : i + batch_size]
        for i in range(0, len(resort_list), batch_size)
    ]
    if limit_batches is not None:
        batches = batches[:limit_batches]

    total_batches = len(batches)
    max_workers = min(5, total_batches) if batches else 1
    records: list[dict] = []
    merge_log: list[dict] = []
    progress = _Progress(f"Phase 2 — attributes run {run_num}", total=total_batches)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _fetch_attribute_batch, idx, batch, cfg, run_num, raw, progress,
            ): idx
            for idx, batch in enumerate(batches)
        }
        results_by_idx: dict[int, tuple[list[dict], list[dict]]] = {}
        for future in as_completed(futures):
            idx = futures[future]
            results_by_idx[idx] = future.result()

    for idx in range(total_batches):
        if idx in results_by_idx:
            batch_recs, batch_log = results_by_idx[idx]
            records.extend(batch_recs)
            merge_log.extend(batch_log)

    progress.finish(f"{len(records)} records from {total_batches} batches")
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
    return merge_resort_runs(runs_df)


def run(
    cfg: dict,
    limit_batches: int | None = None,
    single_run: int | None = None,
) -> None:
    """Full C1 pipeline. Attribute runs execute in parallel."""
    processed = processed_dir(cfg)
    processed.mkdir(parents=True, exist_ok=True)

    resort_list, list_merge_log = fetch_resort_list(cfg, limit_batches=limit_batches)

    if not resort_list:
        logger.error("No resorts found")
        raise SystemExit(3)

    runs_to_do = [single_run] if single_run else list(range(1, cfg["llm"]["runs"] + 1))
    all_run_records: list[dict] = []
    all_merge_log: list[dict] = list(list_merge_log)

    with ThreadPoolExecutor(max_workers=len(runs_to_do)) as pool:
        futures = {
            pool.submit(
                fetch_resort_attributes,
                resort_list, cfg, run_num, limit_batches,
            ): run_num
            for run_num in runs_to_do
        }
        results_by_run: dict[int, tuple[list[dict], list[dict]]] = {}
        for future in as_completed(futures):
            run_num = futures[future]
            results_by_run[run_num] = future.result()

    for run_num in runs_to_do:
        records, merge_log = results_by_run[run_num]
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
