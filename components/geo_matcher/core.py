"""C3: Link restaurants to resorts by coordinate distance."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common.contract_io import read_csv, write_csv
from common.geo import haversine
from common.log import get_logger
from common.paths import processed_dir

logger = get_logger("geo_matcher")


def match_restaurants(resorts_df: pd.DataFrame, restaurants_df: pd.DataFrame,
                      cfg: dict) -> pd.DataFrame:
    """Match each restaurant to its nearest resort within radius."""
    radius_km = cfg["matching"]["radius_km"]
    ambiguity_km = cfg["matching"]["ambiguity_km"]

    matches = []
    for _, rest in restaurants_df.iterrows():
        distances = []
        for _, resort in resorts_df.iterrows():
            d = haversine(rest["lat"], rest["lon"], resort["lat"], resort["lon"])
            max_r = radius_km.get(resort["size_class"], 8)
            distances.append({
                "resort_id": resort["resort_id"],
                "resort_name": resort["name"],
                "distance_km": round(d, 2),
                "max_radius": max_r,
                "within_radius": d <= max_r,
            })

        distances.sort(key=lambda x: x["distance_km"])
        in_radius = [d for d in distances if d["within_radius"]]

        if not in_radius:
            nearest = distances[0] if distances else None
            matches.append({
                "restaurant_id": rest["restaurant_id"],
                "resort_id": None,
                "distance_km": nearest["distance_km"] if nearest else None,
                "second_resort_id": None,
                "second_distance_km": None,
                "match_status": "unmatched",
                "hint_agrees": None,
            })
        else:
            nearest = in_radius[0]
            second = in_radius[1] if len(in_radius) > 1 else None
            if second is None and len(distances) > 1:
                second = distances[1]

            is_ambiguous = (
                second is not None
                and second["within_radius"]
                and (second["distance_km"] - nearest["distance_km"]) < ambiguity_km
            )

            hint = rest.get("ski_area_hint")
            hint_agrees = None
            if hint and isinstance(hint, str) and nearest["resort_name"]:
                h = hint.lower().strip()
                rn = nearest["resort_name"].lower()
                hint_agrees = h in rn or rn in h

            matches.append({
                "restaurant_id": rest["restaurant_id"],
                "resort_id": nearest["resort_id"],
                "distance_km": nearest["distance_km"],
                "second_resort_id": second["resort_id"] if second else None,
                "second_distance_km": second["distance_km"] if second else None,
                "match_status": "ambiguous" if is_ambiguous else "matched",
                "hint_agrees": hint_agrees,
            })

    return pd.DataFrame(matches)


def compute_resort_lunch(matches_df: pd.DataFrame, restaurants_df: pd.DataFrame,
                         resorts_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Compute median lunch price per resort from matched restaurants."""
    min_restaurants = cfg["matching"]["min_restaurants"]

    matched = matches_df[matches_df["resort_id"].notna()].merge(
        restaurants_df[["restaurant_id", "lunch_main_eur", "lunch_drink_eur", "country"]],
        on="restaurant_id",
    )

    country_medians = restaurants_df.groupby("country").agg(
        lunch_main_median=("lunch_main_eur", "median"),
        lunch_drink_median=("lunch_drink_eur", "median"),
    ).to_dict("index")

    rows = []
    for _, resort in resorts_df.iterrows():
        rid = resort["resort_id"]
        resort_matches = matched[matched["resort_id"] == rid]
        n = len(resort_matches)

        if n >= min_restaurants:
            main_eur = round(float(resort_matches["lunch_main_eur"].median()), 2)
            drink_eur = round(float(resort_matches["lunch_drink_eur"].median()), 2)
            if n >= 4:
                iqr = round(
                    float(resort_matches["lunch_main_eur"].quantile(0.75)
                          - resort_matches["lunch_main_eur"].quantile(0.25)),
                    2,
                )
            else:
                iqr = None
            source = "matched"
        else:
            country = resort["country"]
            cm = country_medians.get(
                country, {"lunch_main_median": 18.0, "lunch_drink_median": 4.5}
            )
            main_eur = round(float(cm["lunch_main_median"]), 2)
            drink_eur = round(float(cm["lunch_drink_median"]), 2)
            iqr = None
            source = "country_median"

        rows.append({
            "resort_id": rid,
            "n_restaurants": n,
            "lunch_main_eur": main_eur,
            "lunch_drink_eur": drink_eur,
            "lunch_iqr_eur": iqr,
            "lunch_source": source,
        })

    return pd.DataFrame(rows)


def run(cfg: dict):
    """Run the geo matcher: read I1 + I2, produce I3."""
    proc = processed_dir(cfg)

    resorts_df = read_csv(Path(proc) / "resorts.csv", "resort_table")
    restaurants_df = read_csv(Path(proc) / "restaurants.csv", "restaurant_table")

    matches_df = match_restaurants(resorts_df, restaurants_df, cfg)
    resort_lunch_df = compute_resort_lunch(
        matches_df, restaurants_df, resorts_df, cfg
    )

    inputs = [
        str(Path(proc) / "resorts.csv"),
        str(Path(proc) / "restaurants.csv"),
    ]
    write_csv(
        matches_df, Path(proc) / "matches.csv", "matches",
        "geo_matcher@1.0.0", inputs=inputs,
    )
    write_csv(
        resort_lunch_df, Path(proc) / "resort_lunch.csv", "resort_lunch",
        "geo_matcher@1.0.0", inputs=inputs,
    )

    n_matched = len(matches_df[matches_df["match_status"] == "matched"])
    n_ambiguous = len(matches_df[matches_df["match_status"] == "ambiguous"])
    n_unmatched = len(matches_df[matches_df["match_status"] == "unmatched"])
    logger.info(
        f"Matched {n_matched}, ambiguous {n_ambiguous}, unmatched {n_unmatched}"
    )
