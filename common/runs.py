import statistics
from collections import Counter

import pandas as pd


def merge_numeric(values):
    clean = [v for v in values if v is not None and pd.notna(v)]
    if not clean:
        return (None, None, None)
    med = statistics.median(clean)
    sd = statistics.stdev(clean) if len(clean) > 1 else 0.0
    rng = max(clean) - min(clean)
    return (med, round(sd, 4), round(rng, 4))


def merge_categorical(values):
    clean = [v for v in values if v is not None and pd.notna(v)]
    if not clean:
        return (None, None)
    counter = Counter(clean)
    mode = counter.most_common(1)[0][0]
    agreement = counter[mode] / len(clean)
    return (mode, round(agreement, 4))


RESORT_NUMERIC = [
    "top_elevation_m", "base_elevation_m", "slope_km",
    "day_pass_adult_eur", "day_pass_youth16_eur", "day_pass_child13_eur",
    "family_pass_eur", "drive_time_min", "drive_distance_km",
    "snow_reliability", "family_friendliness", "value_for_money",
]

RESORT_CATEGORICAL = ["size_class", "confidence"]

RESORT_TEXT = [
    "reason_snow", "reason_family", "reason_value",
    "age_category_16", "age_category_13",
    "family_pass_conditions",
]


def merge_resort_runs(runs_df):
    grouped = runs_df.groupby("resort_id")
    rows = []
    for rid, group in grouped:
        row = {"resort_id": rid}
        first = group.iloc[0]
        for col in ["name", "country", "region", "lat", "lon"]:
            if col in group.columns:
                row[col] = first[col]

        for col in RESORT_NUMERIC:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            med, sd, rng = merge_numeric(vals)
            row[col] = med
            row[f"{col}_sd"] = sd
            row[f"{col}_range"] = rng

        for col in RESORT_CATEGORICAL:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            mode, agreement = merge_categorical(vals)
            row[col] = mode
            row[f"{col}_agreement"] = agreement

        for col in RESORT_TEXT:
            if col not in group.columns:
                continue
            row[col] = first[col]

        row["n_runs_valid"] = len(group)
        rows.append(row)
    return pd.DataFrame(rows)


RESTAURANT_NUMERIC = [
    "lat", "lon", "elevation_m", "lunch_main_eur", "lunch_drink_eur",
]

RESTAURANT_CATEGORICAL = ["restaurant_type", "price_level", "confidence"]

RESTAURANT_TEXT = ["reason_price", "ski_area_hint"]


def merge_restaurant_runs(runs_df):
    grouped = runs_df.groupby("restaurant_id")
    rows = []
    for rid, group in grouped:
        row = {"restaurant_id": rid}
        first = group.iloc[0]
        for col in ["name", "country", "region"]:
            if col in group.columns:
                row[col] = first[col]

        for col in RESTAURANT_NUMERIC:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            med, sd, rng = merge_numeric(vals)
            row[col] = med
            if col in ("lunch_main_eur",):
                row[f"{col}_sd"] = sd

        for col in RESTAURANT_CATEGORICAL:
            if col not in group.columns:
                continue
            vals = group[col].tolist()
            mode, agreement = merge_categorical(vals)
            row[col] = mode

        for col in RESTAURANT_TEXT:
            if col not in group.columns:
                continue
            row[col] = first[col]

        row["n_runs_valid"] = len(group)
        rows.append(row)
    return pd.DataFrame(rows)
