"""C1 resort_source – fetch ski resort data from real sources + LLM ratings."""

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
from common.paths import raw_dir, processed_dir, figures_dir
from common.runs import merge_resort_runs
from components.llm_gateway import generate_json

logger = get_logger("resort_source")

RATING_FIELDS = ["snow_reliability", "family_friendliness", "value_for_money"]
RATING_CATEGORICAL = ["confidence"]
RATING_TEXT = ["reason_snow", "reason_family", "reason_value"]


class _Progress:
    """Thread-safe progress tracker with stderr status line."""

    def __init__(self, phase: str, total: int | None = None):
        self._lock = Lock()
        self._phase = phase
        self._total = total
        self._done = 0
        self._skipped = 0
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
        parts.append(f"  {elapsed:.0f}s")
        sys.stderr.write("".join(parts) + "   \r")
        sys.stderr.flush()

    def finish(self, msg: str = "") -> None:
        elapsed = time.monotonic() - self._start
        line = f"\r  {self._phase}: {msg}  ({elapsed:.1f}s)"
        sys.stderr.write(line + " " * 20 + "\n")
        sys.stderr.flush()


def _size_class(slope_km: float | None) -> str:
    if slope_km is None:
        return "small"
    if slope_km < 30:
        return "small"
    if slope_km <= 100:
        return "medium"
    return "large"


def _fetch_rating_batch(
    batch_idx: int,
    batch: list[dict],
    cfg: dict,
    run_num: int,
    raw: Path,
    progress: _Progress | None = None,
) -> tuple[list[dict], list[dict]]:
    """Fetch LLM ratings for one batch of resorts."""
    records: list[dict] = []
    merge_log: list[dict] = []

    out_path = raw / f"resort_ratings_run{run_num}" / f"batch{batch_idx}.json"
    was_cached = out_path.exists()
    if was_cached:
        logger.info("Resuming: %s exists, loading", out_path)
        envelope = json.loads(out_path.read_text("utf-8"))
        batch_records = envelope.get("records", [])
    else:
        batch_list_str = "\n".join(
            f"- {r['resort_id']}: {r['name']} ({r['country']}"
            f", {r.get('slope_km', '?')} km pistes"
            f", drive {r.get('drive_time_min', '?')} min"
            f", adult pass {r.get('day_pass_adult_eur', '?')} EUR"
            f", lat={r['lat']}, lon={r['lon']})"
            for r in batch
        )
        result = generate_json(
            template_id="resort_ratings",
            variables={"batch_list": batch_list_str},
            record_schema_id="resort_rating_record",
            temperature=cfg["llm"]["temperature_subjective"],
            out_path=out_path,
            cfg=cfg,
            kind="resort_ratings",
        )
        if not result.ok:
            logger.warning("Ratings failed run %d batch %d: %s", run_num, batch_idx, result.error)
            return records, merge_log
        batch_records = result.records

    expected_ids = {r["resort_id"] for r in batch}
    for rec in batch_records:
        rid = rec.get("resort_id")
        if rid and rid not in expected_ids:
            merge_log.append({
                "batch_id": f"run{run_num}_batch{batch_idx}",
                "item_id": rid,
                "record_name": rid,
                "reason": "unknown_item",
                "detail": f"resort_id '{rid}' not in batch",
            })
            continue

        rec["run"] = run_num
        records.append(rec)

    if progress:
        progress.tick(skipped=was_cached)

    return records, merge_log


def fetch_resort_ratings(
    resort_list: list[dict],
    cfg: dict,
    run_num: int,
    limit_batches: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Fetch LLM subjective ratings for all resorts."""
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
    progress = _Progress(f"Phase 4 — LLM ratings run {run_num}", total=total_batches)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _fetch_rating_batch, idx, batch, cfg, run_num, raw, progress,
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
    logger.info("Run %d: %d valid rating records", run_num, len(records))
    return records, merge_log


def _merge_ratings(all_run_records: list[dict]) -> pd.DataFrame:
    """Merge multiple LLM rating runs into median/SD/range."""
    if not all_run_records:
        return pd.DataFrame()

    cols = ["resort_id", "run"] + RATING_FIELDS + RATING_CATEGORICAL + RATING_TEXT
    rows = [{c: rec.get(c) for c in cols} for rec in all_run_records]
    runs_df = pd.DataFrame(rows, columns=cols)

    grouped = runs_df.groupby("resort_id")
    merged_rows = []
    for rid, group in grouped:
        row = {"resort_id": rid}

        from common.runs import merge_numeric, merge_categorical
        for col in RATING_FIELDS:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            med, sd, rng = merge_numeric(vals)
            row[col] = med
            row[f"{col}_sd"] = sd
            row[f"{col}_range"] = rng

        for col in RATING_CATEGORICAL:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            mode, agreement = merge_categorical(vals)
            row[col] = mode
            row[f"{col}_agreement"] = agreement

        for col in RATING_TEXT:
            if col in group.columns:
                row[col] = group.iloc[0][col]

        row["n_runs_valid"] = len(group)
        merged_rows.append(row)

    return pd.DataFrame(merged_rows)


def run(
    cfg: dict,
    limit_batches: int | None = None,
    single_run: int | None = None,
) -> None:
    """Full C1 pipeline with real data sources + LLM ratings."""
    processed = processed_dir(cfg)
    processed.mkdir(parents=True, exist_ok=True)

    # --- Phase 1: OpenSkiData Resort List ---
    logger.info("=== Phase 1: Fetching resort list from OpenSkiData ===")
    from components.resort_source.osm import fetch_osm_resorts
    osm_resorts = fetch_osm_resorts(cfg)

    if not osm_resorts:
        logger.error("No resorts found from OpenSkiData")
        raise SystemExit(3)

    logger.info("Phase 1 complete: %d resorts from OpenSkiData", len(osm_resorts))

    # --- Phase 2: OSRM Routing ---
    logger.info("=== Phase 2: Fetching driving data from OSRM ===")
    from components.resort_source.routing import fetch_routes
    routes = fetch_routes(osm_resorts, cfg)

    max_drive = cfg["costs"]["max_drive_time_min"]
    reachable = []
    for r in osm_resorts:
        route = routes.get(r["resort_id"], {})
        drive_time = route.get("drive_time_min")
        if drive_time is not None and drive_time <= max_drive:
            r["drive_time_min"] = drive_time
            r["drive_distance_km"] = route.get("drive_distance_km")
            reachable.append(r)
        elif drive_time is None:
            r["drive_time_min"] = None
            r["drive_distance_km"] = None
            reachable.append(r)

    logger.info("Phase 2 complete: %d reachable resorts (of %d, max %d min)",
                len(reachable), len(osm_resorts), max_drive)

    if not reachable:
        logger.error("No reachable resorts")
        raise SystemExit(3)

    # --- Phase 3: Scraping prices + physical data ---
    logger.info("=== Phase 3: Scraping prices from skiresort.de ===")
    from components.resort_source.scraper import (
        scrape_resorts, impute_missing_prices, generate_provenance_chart,
    )
    scrape_results, report_df = scrape_resorts(reachable, cfg)

    report_df["country"] = report_df["resort_id"].map(
        {r["resort_id"]: r["country"] for r in reachable}
    )

    scrape_results, report_df = impute_missing_prices(reachable, scrape_results, report_df)

    scrape_by_id = {sr["resort_id"]: sr for sr in scrape_results}
    for r in reachable:
        sr = scrape_by_id.get(r["resort_id"], {})
        for field in [
            "day_pass_adult_eur", "day_pass_youth16_eur", "day_pass_child13_eur",
            "family_pass_eur", "age_category_16", "age_category_13",
            "family_pass_conditions",
        ]:
            if sr.get(field) is not None:
                r[field] = sr[field]
            else:
                r.setdefault(field, None)

        # slope_km and elevations come from OpenSkiData (Phase 1), scraper only supplements if missing
        for field in ["slope_km", "top_elevation_m", "base_elevation_m"]:
            if r.get(field) is None and sr.get(field) is not None:
                r[field] = sr[field]
            r.setdefault(field, None)

        r["source_prices"] = sr.get("source_url") if sr.get("status") == "scraped" else (
            "estimated:country_size_median" if sr.get("status") == "estimated" else None
        )
        r["source_physical"] = "openskidata" if r.get("slope_km") is not None else None

    report_path = processed / "scraping_report.csv"
    report_df.to_csv(report_path, index=False, encoding="utf-8")
    logger.info("Scraping report: %s (%d rows)", report_path, len(report_df))

    figs = figures_dir(cfg)
    generate_provenance_chart(report_df, figs)

    for r in reachable:
        r["size_class"] = _size_class(r.get("slope_km"))
        r["source_coords"] = "openskidata"
        r["source_driving"] = "osrm"
        r["source_ratings"] = "llm"

    # --- Phase 4: LLM Ratings (subjective only) ---
    logger.info("=== Phase 4: Fetching LLM ratings ===")
    runs_to_do = [single_run] if single_run else list(range(1, cfg["llm"]["runs"] + 1))
    all_run_records: list[dict] = []
    all_merge_log: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(runs_to_do)) as pool:
        futures = {
            pool.submit(
                fetch_resort_ratings,
                reachable, cfg, run_num, limit_batches,
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

    ratings_df = _merge_ratings(all_run_records)
    logger.info("Phase 4 complete: %d resorts with merged ratings", len(ratings_df))

    # --- Phase 5: Merge real data + LLM ratings → resorts.csv ---
    logger.info("=== Phase 5: Building final resorts.csv ===")
    resort_df = pd.DataFrame(reachable)

    if not ratings_df.empty:
        rating_cols = ["resort_id"] + RATING_FIELDS + [
            f"{f}_sd" for f in RATING_FIELDS
        ] + [
            f"{f}_range" for f in RATING_FIELDS
        ] + RATING_CATEGORICAL + [
            f"{c}_agreement" for c in RATING_CATEGORICAL
        ] + RATING_TEXT + ["n_runs_valid"]
        rating_cols = [c for c in rating_cols if c in ratings_df.columns]
        resort_df = resort_df.merge(
            ratings_df[rating_cols], on="resort_id", how="left",
        )
    else:
        for f in RATING_FIELDS:
            resort_df[f] = None
            resort_df[f"{f}_sd"] = None
            resort_df[f"{f}_range"] = None
        for c in RATING_CATEGORICAL:
            resort_df[c] = None
            resort_df[f"{c}_agreement"] = None
        for t in RATING_TEXT:
            resort_df[t] = None
        resort_df["n_runs_valid"] = 0

    for col in ["day_pass_adult_eur", "day_pass_youth16_eur", "day_pass_child13_eur",
                 "family_pass_eur", "drive_time_min", "drive_distance_km",
                 "slope_km", "top_elevation_m", "base_elevation_m"]:
        resort_df[f"{col}_sd"] = 0.0
        resort_df[f"{col}_range"] = 0.0

    for col in ["age_category_16", "age_category_13"]:
        if col in resort_df.columns:
            resort_df[f"{col}_agreement"] = 1.0

    resort_df["size_class_agreement"] = 1.0

    drop_cols = ["openskidata_id", "website", "_size_class", "lift_count", "sources"]
    resort_df = resort_df.drop(columns=[c for c in drop_cols if c in resort_df.columns], errors="ignore")

    if "region" not in resort_df.columns:
        resort_df["region"] = ""
    resort_df["region"] = resort_df["region"].fillna("")

    if "n_runs_valid" not in resort_df.columns:
        resort_df["n_runs_valid"] = 0
    resort_df["n_runs_valid"] = resort_df["n_runs_valid"].fillna(0).astype(int)

    from common.contract_io import write_csv
    resorts_path = processed / "resorts.csv"
    write_csv(resort_df, resorts_path, "resort_table", "resort_source@2.0.0")

    if all_merge_log:
        log_df = pd.DataFrame(all_merge_log)
        log_path = processed / "resorts_merge_log.csv"
        log_df.to_csv(log_path, index=False, encoding="utf-8")
        logger.info("Wrote %s (%d entries)", log_path, len(log_df))

    min_items = cfg["resorts"]["min_items"]
    if len(resort_df) < min_items:
        logger.error("Only %d resorts, need at least %d", len(resort_df), min_items)
        raise SystemExit(3)

    logger.info("C1 complete: %d resorts with real data + LLM ratings", len(resort_df))
