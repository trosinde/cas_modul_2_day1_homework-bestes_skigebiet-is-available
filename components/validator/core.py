"""C7: Validation – sample generation and multi-level checks."""

from __future__ import annotations

import hashlib
import time

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

from common.contract_io import read_csv, write_csv, write_json
from common.log import get_logger

logger = get_logger("validator")


def generate_sample(
    resorts_df: pd.DataFrame,
    restaurants_df: pd.DataFrame | None,
    matches_df: pd.DataFrame | None,
    cfg: dict,
) -> pd.DataFrame:
    """Generate fact-check sample with empty target values."""
    rows: list[dict] = []

    n_resorts = min(12, len(resorts_df))
    if "value_rank" in resorts_df.columns and resorts_df["value_rank"].notna().any():
        top = resorts_df.nsmallest(3, "value_rank")
    else:
        top = resorts_df.head(3)
    low_conf = resorts_df[resorts_df["confidence"] == "low"].head(3)
    picked_ids = set(top["resort_id"]).union(low_conf["resort_id"])
    pool = resorts_df[~resorts_df["resort_id"].isin(picked_ids)]
    need = max(0, n_resorts - len(picked_ids))
    remaining = pool.sample(min(need, len(pool)), random_state=42)
    sample_resorts = (
        pd.concat([top, low_conf, remaining])
        .drop_duplicates("resort_id")
        .head(n_resorts)
    )

    resort_attrs = [
        "top_elevation_m", "slope_km", "day_pass_adult_eur",
        "day_pass_youth16_eur", "day_pass_child13_eur",
        "age_category_16", "family_pass_eur", "drive_time_min",
        "lat", "lon",
    ]

    for _, resort in sample_resorts.iterrows():
        for attr in resort_attrs:
            if attr in resort.index and pd.notna(resort[attr]):
                if "_m" in attr:
                    unit = "m"
                elif "_eur" in attr:
                    unit = "EUR"
                elif "_min" in attr:
                    unit = "min"
                elif attr in ("lat", "lon"):
                    unit = "deg"
                else:
                    unit = ""
                rows.append({
                    "item_type": "resort",
                    "item_id": resort["resort_id"],
                    "attribute": attr,
                    "llm_value": str(resort[attr]),
                    "unit": unit,
                    "target_value": None,
                    "source_url": None,
                    "checked_on": None,
                    "note": None,
                })

    if restaurants_df is not None and len(restaurants_df) > 0:
        n_rest = min(10, len(restaurants_df))
        sample_rest = restaurants_df.sample(n_rest, random_state=42)
        for _, rest in sample_rest.iterrows():
            for attr in ["lat", "lon", "lunch_main_eur"]:
                if attr in rest.index and pd.notna(rest[attr]):
                    rows.append({
                        "item_type": "restaurant",
                        "item_id": rest["restaurant_id"],
                        "attribute": attr,
                        "llm_value": str(rest[attr]),
                        "unit": "deg" if attr in ("lat", "lon") else "EUR",
                        "target_value": None,
                        "source_url": None,
                        "checked_on": None,
                        "note": None,
                    })

    if matches_df is not None and len(matches_df) > 0:
        matched = matches_df[matches_df["match_status"].isin(["matched", "ambiguous"])]
        n_match = min(15, len(matched))
        if n_match > 0:
            sample_matches = matched.sample(n_match, random_state=42)
            for _, m in sample_matches.iterrows():
                rows.append({
                    "item_type": "match",
                    "item_id": m["restaurant_id"],
                    "attribute": "correct_assignment",
                    "llm_value": str(m["resort_id"]),
                    "unit": "",
                    "target_value": None,
                    "source_url": None,
                    "checked_on": None,
                    "note": None,
                })

    return pd.DataFrame(rows)


def check_fact_accuracy(
    sample_df: pd.DataFrame, tolerance: float
) -> tuple[float, list[dict]]:
    """Check filled fact-check sample against tolerance."""
    filled = sample_df[sample_df["target_value"].notna()].copy()
    if len(filled) == 0:
        return 1.0, []

    flags: list[dict] = []
    correct = 0
    total = 0

    for _, row in filled.iterrows():
        total += 1
        try:
            llm_val = float(row["llm_value"])
            target_val = float(row["target_value"])
            if target_val == 0:
                within = abs(llm_val - target_val) < 1
            else:
                within = abs(llm_val - target_val) / abs(target_val) <= tolerance
            if within:
                correct += 1
            else:
                pct = (
                    abs(llm_val - target_val) / abs(target_val) * 100
                    if target_val != 0
                    else 999
                )
                flags.append({
                    "item_type": row["item_type"],
                    "item_id": row["item_id"],
                    "level": "single_value",
                    "check_id": "fact_check",
                    "attribute": row["attribute"],
                    "severity": "error" if pct > 50 else "warning",
                    "message": (
                        f"LLM={row['llm_value']}, "
                        f"target={row['target_value']} ({pct:.0f}% off)"
                    ),
                })
        except (ValueError, TypeError):
            if (
                str(row["llm_value"]).strip().lower()
                == str(row["target_value"]).strip().lower()
            ):
                correct += 1
            else:
                flags.append({
                    "item_type": row["item_type"],
                    "item_id": row["item_id"],
                    "level": "single_value",
                    "check_id": "fact_check",
                    "attribute": row["attribute"],
                    "severity": "warning",
                    "message": (
                        f"LLM='{row['llm_value']}', "
                        f"target='{row['target_value']}'"
                    ),
                })

    accuracy = correct / total if total > 0 else 1.0
    return accuracy, flags


def check_run_stability(
    runs_df: pd.DataFrame, min_spearman: float, numeric_cols: list[str]
) -> tuple[float, list[dict]]:
    """Check Spearman correlation between runs for numeric attributes."""
    flags: list[dict] = []
    min_corr = 1.0

    for col in numeric_cols:
        if col not in runs_df.columns:
            continue
        pivoted = runs_df.pivot_table(index="resort_id", columns="run", values=col)
        if pivoted.shape[1] < 2:
            continue
        for r1 in pivoted.columns:
            for r2 in pivoted.columns:
                if r1 >= r2:
                    continue
                valid = pivoted[[r1, r2]].dropna()
                if len(valid) < 5:
                    continue
                corr, _ = stats.spearmanr(valid[r1], valid[r2])
                if not np.isnan(corr):
                    min_corr = min(min_corr, corr)
                    if corr < min_spearman:
                        flags.append({
                            "item_type": "resort",
                            "item_id": "",
                            "level": "attribute",
                            "check_id": "run_stability",
                            "attribute": col,
                            "severity": "warning",
                            "message": (
                                f"Spearman r={corr:.2f} between run {r1} "
                                f"and {r2} (threshold: {min_spearman})"
                            ),
                        })
    return min_corr, flags


def check_item_rules(resorts_df: pd.DataFrame) -> list[dict]:
    """Check item-level rules: base < top, coords in Alps, size_class vs slope_km."""
    flags: list[dict] = []
    for _, r in resorts_df.iterrows():
        rid = r["resort_id"]

        if pd.notna(r.get("base_elevation_m")) and pd.notna(r.get("top_elevation_m")):
            if r["base_elevation_m"] >= r["top_elevation_m"]:
                flags.append({
                    "item_type": "resort", "item_id": rid, "level": "item",
                    "check_id": "elevation_order", "attribute": "base_elevation_m",
                    "severity": "error",
                    "message": f"base ({r['base_elevation_m']}) >= top ({r['top_elevation_m']})",
                })

        if pd.notna(r.get("lat")) and pd.notna(r.get("lon")):
            if not (44 <= r["lat"] <= 48.5 and 5 <= r["lon"] <= 17):
                flags.append({
                    "item_type": "resort", "item_id": rid, "level": "item",
                    "check_id": "coords_in_alps", "attribute": "lat",
                    "severity": "warning",
                    "message": f"Coordinates ({r['lat']}, {r['lon']}) outside typical Alps range",
                })

        if pd.notna(r.get("slope_km")) and pd.notna(r.get("size_class")):
            expected = (
                "small" if r["slope_km"] < 30
                else ("medium" if r["slope_km"] <= 100 else "large")
            )
            if r["size_class"] != expected:
                flags.append({
                    "item_type": "resort", "item_id": rid, "level": "item",
                    "check_id": "size_class_match", "attribute": "size_class",
                    "severity": "info",
                    "message": (
                        f"size_class={r['size_class']} but "
                        f"slope_km={r['slope_km']} suggests {expected}"
                    ),
                })
    return flags


def check_correlations(costs_df: pd.DataFrame) -> tuple[bool, list[dict]]:
    """Check expected correlations: elevation-snow, size-price, drive-distance."""
    flags: list[dict] = []
    all_ok = True

    expected = [
        ("top_elevation_m", "snow_reliability", "positive"),
        ("slope_km", "day_pass_adult_eur", "positive"),
        ("drive_time_min", "drive_distance_km", "positive"),
    ]

    for col1, col2, direction in expected:
        if col1 not in costs_df.columns or col2 not in costs_df.columns:
            continue
        valid = costs_df[[col1, col2]].dropna()
        if len(valid) < 5:
            continue
        corr, _ = stats.spearmanr(valid[col1], valid[col2])
        if np.isnan(corr):
            continue
        ok = (direction == "positive" and corr > 0) or (
            direction == "negative" and corr < 0
        )
        if not ok:
            all_ok = False
            flags.append({
                "item_type": "resort", "item_id": "", "level": "dataset",
                "check_id": "expected_correlation",
                "attribute": f"{col1} vs {col2}",
                "severity": "warning",
                "message": f"Expected {direction} correlation, got r={corr:.2f}",
            })
    return all_ok, flags


def check_geo_assignments(
    matches_df: pd.DataFrame,
    resorts_df: pd.DataFrame,
    restaurants_df: pd.DataFrame,
    cfg: dict,
) -> tuple[dict, list[dict]]:
    """Check geo assignment quality."""
    flags: list[dict] = []
    matched = int((matches_df["match_status"] == "matched").sum())
    ambiguous = int((matches_df["match_status"] == "ambiguous").sum())
    unmatched = int((matches_df["match_status"] == "unmatched").sum())

    resorts_with_restaurants = (
        matches_df[matches_df["resort_id"].notna()]["resort_id"].nunique()
    )
    coverage = (
        resorts_with_restaurants / len(resorts_df) if len(resorts_df) > 0 else 0
    )

    hint_checks = matches_df[matches_df["hint_agrees"].notna()]
    hint_rate = float(hint_checks["hint_agrees"].mean()) if len(hint_checks) > 0 else None

    if coverage < cfg["acceptance"]["min_match_coverage"]:
        flags.append({
            "item_type": "match", "item_id": "", "level": "dataset",
            "check_id": "match_coverage", "attribute": "coverage",
            "severity": "warning",
            "message": (
                f"Coverage {coverage:.1%} below threshold "
                f"{cfg['acceptance']['min_match_coverage']:.0%}"
            ),
        })

    return {
        "total": matched + ambiguous + unmatched,
        "matched": matched,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "coverage": round(coverage, 3),
        "hint_agreement": round(hint_rate, 3) if hint_rate is not None else None,
    }, flags


def build_report(all_flags: list[dict], summary: dict, cfg: dict) -> dict:
    """Build validation_report.json."""
    config_hash = ""
    try:
        with open("config.yaml", "rb") as f:
            config_hash = hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        pass

    criteria = cfg["acceptance"]
    issues: list[str] = []
    if summary.get("fact_check_accuracy", 1) < (1 - criteria["fact_check_tolerance"]):
        issues.append("fact_check_below_threshold")
    if summary.get("spearman_min", 1) < criteria["min_spearman"]:
        issues.append("run_stability_below_threshold")
    if summary.get("fabricated_items", 0) > 0:
        issues.append("fabricated_items_found")

    if not issues:
        recommendation = "go"
    elif len(issues) <= 1:
        recommendation = "conditional_go"
    else:
        recommendation = "no_go"

    return {
        "schema_version": "1.0.0",
        "produced_by": "validator@1.0.0",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_sha256": config_hash,
        "summary": summary,
        "checks": all_flags,
        "recommendation": recommendation,
        "reasoning": (
            f"{'No' if not issues else len(issues)} issues found: "
            f"{', '.join(issues) if issues else 'all criteria met'}"
        ),
    }


# ── entry points ──────────────────────────────────────────────


def run_sample(cfg: dict) -> None:
    """Generate empty fact-check sample."""
    from common.paths import processed_dir

    proc = Path(processed_dir(cfg))

    resorts_df = read_csv(proc / "resorts.csv", "resort_table")

    restaurants_df = None
    if (proc / "restaurants.csv").exists():
        restaurants_df = read_csv(proc / "restaurants.csv", "restaurant_table")

    matches_df = None
    if (proc / "matches.csv").exists():
        matches_df = read_csv(proc / "matches.csv", "matches")

    sample = generate_sample(resorts_df, restaurants_df, matches_df, cfg)
    sample_path = Path("task5_validation") / "fact_check_sample.csv"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(
        sample, sample_path, "fact_check", "validator@1.0.0",
        inputs=[str(proc / "resorts.csv")],
    )
    logger.info("Generated fact-check sample with %d entries", len(sample))
    print(f"  Fact-check sample: {len(sample)} Einträge")


def run_validate(cfg: dict) -> dict:
    """Run all validation checks."""
    from common.paths import processed_dir

    proc = Path(processed_dir(cfg))

    resorts_df = read_csv(proc / "resorts.csv", "resort_table")
    costs_df = read_csv(proc / "resorts_costs.csv", "cost_table")

    all_flags: list[dict] = []
    summary: dict = {}

    # Fact check
    sample_path = Path("task5_validation") / "fact_check_sample.csv"
    if sample_path.exists():
        sample_df = read_csv(sample_path, "fact_check")
        acc, fc_flags = check_fact_accuracy(
            sample_df, cfg["acceptance"]["fact_check_tolerance"]
        )
        all_flags.extend(fc_flags)
        summary["fact_check_accuracy"] = round(acc, 3)

    # Run stability
    runs_path = proc / "resorts_runs.csv"
    if runs_path.exists():
        runs_df = read_csv(runs_path, "resort_runs")
        numeric_cols = [
            "snow_reliability", "family_friendliness", "value_for_money",
            "top_elevation_m", "slope_km", "day_pass_adult_eur",
        ]
        min_corr, stab_flags = check_run_stability(
            runs_df, cfg["acceptance"]["min_spearman"], numeric_cols
        )
        all_flags.extend(stab_flags)
        summary["spearman_min"] = round(min_corr, 3)

    # Item rules
    item_flags = check_item_rules(resorts_df)
    all_flags.extend(item_flags)

    # Age category accuracy (filled after manual check)
    summary["age_category_accuracy"] = None

    # Correlations
    _, corr_flags = check_correlations(costs_df)
    all_flags.extend(corr_flags)

    # Geo checks
    if (proc / "matches.csv").exists():
        matches_df = read_csv(proc / "matches.csv", "matches")
        restaurants_df = read_csv(proc / "restaurants.csv", "restaurant_table")
        geo_summary, geo_flags = check_geo_assignments(
            matches_df, resorts_df, restaurants_df, cfg
        )
        all_flags.extend(geo_flags)
        summary["match_coverage"] = geo_summary["coverage"]
        summary["match_hit_rate"] = geo_summary.get("hint_agreement")

    # Placeholders
    summary["top5_stable"] = None
    summary["fabricated_items"] = 0

    report = build_report(all_flags, summary, cfg)

    out_dir = Path("task5_validation") / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        report, out_dir / "validation_report.json",
        "validation_report", "validator@1.0.0",
    )

    if all_flags:
        flags_df = pd.DataFrame(all_flags)
    else:
        flags_df = pd.DataFrame(
            columns=[
                "item_type", "item_id", "level", "check_id",
                "attribute", "severity", "message",
            ]
        )
    write_csv(
        flags_df, out_dir / "validation_flags.csv",
        "validation_flags", "validator@1.0.0",
    )

    logger.info(
        "Validation complete: %s (%d flags)",
        report["recommendation"], len(all_flags),
    )
    print(f"  Validation: {report['recommendation']} ({len(all_flags)} Flags)")
    return report


def run(cfg: dict, mode: str = "sample") -> None:
    if mode == "sample":
        run_sample(cfg)
    elif mode == "validate":
        run_validate(cfg)
