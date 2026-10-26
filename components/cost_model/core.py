"""C4 – Cost model: family day costs, quality score, value index, ranking."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from common.contract_io import read_csv, write_csv
from common.log import get_logger

logger = get_logger("cost_model")


def compute_costs(
    resorts_df: pd.DataFrame,
    resort_lunch_df: pd.DataFrame | None,
    cfg: dict,
) -> pd.DataFrame:
    """Compute family day costs and value index for all resorts."""
    cost_per_km = cfg["costs"]["cost_per_km"]
    max_drive = cfg["costs"]["max_drive_time_min"]
    default_variant = cfg["costs"]["default_variant"]
    weights = cfg["quality"]["weights"]
    include_lunch = cfg.get("include_lunch_cost", False)

    df = resorts_df.copy()

    # Join lunch data if available
    if resort_lunch_df is not None:
        lunch_cols = ["resort_id", "lunch_main_eur", "lunch_drink_eur", "lunch_source"]
        lunch_cols = [c for c in lunch_cols if c in resort_lunch_df.columns]
        df = df.merge(
            resort_lunch_df[lunch_cols],
            on="resort_id",
            how="left",
            suffixes=("", "_lunch"),
        )
        for col in ("lunch_main_eur", "lunch_drink_eur", "lunch_source"):
            suffixed = f"{col}_lunch"
            if suffixed in df.columns:
                df[col] = df[suffixed]
                df.drop(columns=[suffixed], inplace=True)

    # --- Family pass cost: min(individual sum, family pass) ---
    individual = (
        2 * df["day_pass_adult_eur"]
        + df["day_pass_youth16_eur"]
        + df["day_pass_child13_eur"]
    )
    has_family = df["family_pass_eur"].notna()
    df["family_pass_cost_eur"] = np.where(
        has_family & (df["family_pass_eur"] < individual),
        df["family_pass_eur"],
        individual,
    ).round(2)
    df["family_pass_used"] = has_family & (df["family_pass_eur"] < individual)

    # --- Travel cost: round trip ---
    df["travel_cost_eur"] = (2 * df["drive_distance_km"] * cost_per_km).round(2)

    # --- Lunch cost: 4 persons × (main + drink) ---
    if resort_lunch_df is not None and "lunch_main_eur" in df.columns:
        df["lunch_cost_eur"] = (
            4 * (df["lunch_main_eur"] + df["lunch_drink_eur"])
        ).round(2)
    else:
        df["lunch_cost_eur"] = np.nan
        df["lunch_source"] = None

    for tmp_col in ("lunch_main_eur", "lunch_drink_eur"):
        if tmp_col in df.columns:
            df.drop(columns=[tmp_col], inplace=True)

    # --- Three cost variants (always computed) ---
    df["day_cost_v1_eur"] = df["family_pass_cost_eur"].round(2)
    df["day_cost_v2_eur"] = (
        df["family_pass_cost_eur"] + df["travel_cost_eur"]
    ).round(2)

    if "lunch_cost_eur" in df.columns and df["lunch_cost_eur"].notna().any():
        df["day_cost_v3_eur"] = (
            df["day_cost_v2_eur"] + df["lunch_cost_eur"]
        ).round(2)
    else:
        df["day_cost_v3_eur"] = np.nan

    # --- Active variant ---
    if include_lunch and "day_cost_v3_eur" in df.columns and df["day_cost_v3_eur"].notna().any():
        df["family_day_cost_eur"] = df["day_cost_v3_eur"]
    elif default_variant == "v2":
        df["family_day_cost_eur"] = df["day_cost_v2_eur"]
    else:
        df["family_day_cost_eur"] = df["day_cost_v1_eur"]

    # --- Size norm: log-dampened ---
    max_slope = df["slope_km"].max()
    log_max = math.log(max(max_slope, 2))
    df["size_norm"] = (np.log(df["slope_km"].clip(lower=1)) / log_max).round(4)

    # --- Quality score: weighted sum (size_norm scaled to 0-10) ---
    df["quality_score"] = (
        weights["snow_reliability"] * df["snow_reliability"]
        + weights["family_friendliness"] * df["family_friendliness"]
        + weights["size_norm"] * df["size_norm"] * 10
    ).round(2)

    # --- Value indices ---
    df["value_index_v1"] = (
        df["quality_score"] / (df["day_cost_v1_eur"] / 100)
    ).round(4)
    df["value_index_v2"] = (
        df["quality_score"] / (df["day_cost_v2_eur"] / 100)
    ).round(4)
    if df["day_cost_v3_eur"].notna().any():
        df["value_index_v3"] = np.where(
            df["day_cost_v3_eur"].notna(),
            (df["quality_score"] / (df["day_cost_v3_eur"] / 100)).round(4),
            np.nan,
        )
    else:
        df["value_index_v3"] = np.nan

    df["value_index"] = (
        df["quality_score"] / (df["family_day_cost_eur"] / 100)
    ).round(4)

    # --- Ranking ---
    df["in_ranking"] = (df["drive_time_min"] <= max_drive) & (df["n_runs_valid"] >= 2)
    ranked = df.loc[df["in_ranking"]].copy()
    ranked["value_rank"] = (
        ranked["value_index"].rank(ascending=False, method="min").astype("Int64")
    )
    df = df.merge(ranked[["resort_id", "value_rank"]], on="resort_id", how="left")

    return df


def run(cfg: dict) -> None:
    """Run cost model: read I1 (+ optional I3), write I4."""
    from common.paths import processed_dir

    proc = processed_dir(cfg)

    resorts_df = read_csv(Path(proc) / "resorts.csv", "resort_table")

    resort_lunch_df = None
    lunch_path = Path(proc) / "resort_lunch.csv"
    if lunch_path.exists():
        resort_lunch_df = read_csv(lunch_path, "resort_lunch")

    costs_df = compute_costs(resorts_df, resort_lunch_df, cfg)

    inputs = [str(Path(proc) / "resorts.csv")]
    if resort_lunch_df is not None:
        inputs.append(str(lunch_path))

    write_csv(
        costs_df,
        Path(proc) / "resorts_costs.csv",
        "cost_table",
        "cost_model@1.0.0",
        inputs=inputs,
    )

    in_rank = costs_df["in_ranking"].sum()
    logger.info(f"Computed costs for {len(costs_df)} resorts, {in_rank} in ranking")
    print(f"  {len(costs_df)} Skigebiete berechnet, {in_rank} im Ranking")
