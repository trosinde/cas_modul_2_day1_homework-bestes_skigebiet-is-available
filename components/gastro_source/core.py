"""C2: Fetch mountain restaurant data – independent of resort data."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from common.config import load as load_config
from common.ids import restaurant_id, slugify
from common.log import get_logger
from common.paths import raw_dir, processed_dir
from common.runs import merge_restaurant_runs

logger = get_logger("gastro_source")


def _normalize(name: str) -> str:
    return " ".join(name.lower().split())


def fetch_restaurant_list(cfg: dict, region_entry: dict,
                          existing_names: list[str] | None = None,
                          limit_batches: int | None = None) -> list[dict]:
    """Fetch restaurant list for one search region via LLM."""
    from components.llm_gateway.core import generate_json

    country = region_entry["country"]
    region = region_entry["region"]
    batch_size = cfg.get("gastro", {}).get("batch_size", 10)
    temperature = cfg["llm"]["temperature_factual"]

    raw = raw_dir(cfg, "gastro_source")
    Path(raw).mkdir(parents=True, exist_ok=True)

    existing = set(_normalize(n) for n in (existing_names or []))
    all_items: list[dict] = []

    region_slug = slugify(region)
    out_path = Path(raw) / "gastro_items" / f"{country.lower()}_{region_slug}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        import json
        envelope = json.loads(out_path.read_text(encoding="utf-8"))
        for rec in envelope.get("records", []):
            n = _normalize(rec.get("name", ""))
            if n and n not in existing:
                existing.add(n)
                rec["country"] = country
                rec["region"] = region
                all_items.append(rec)
        logger.info(f"Resumed {len(all_items)} restaurants from {out_path}")
        return all_items

    variables = {
        "batch_size": batch_size,
        "country": country,
        "country_code": country,
        "region": region,
        "existing_names": ", ".join(sorted(existing)) if existing else "(none)",
    }

    result = generate_json(
        template_id="gastro_items",
        variables=variables,
        record_schema_id="restaurant_record",
        temperature=temperature,
        out_path=out_path,
        cfg=cfg,
        kind="gastro_items",
    )

    if not result.ok:
        logger.warning(f"Failed to fetch restaurants for {country}/{region}: {result.error}")
        return []

    for rec in result.records:
        n = _normalize(rec.get("name", ""))
        if n and n not in existing:
            existing.add(n)
            rec.setdefault("country", country)
            rec.setdefault("region", region)
            all_items.append(rec)

    logger.info(f"Fetched {len(all_items)} restaurants for {country}/{region}")
    return all_items


def fetch_restaurant_prices(restaurant_list: list[dict], cfg: dict,
                            run_number: int,
                            limit_batches: int | None = None) -> list[dict]:
    """Fetch prices for restaurants in batches for one run."""
    from components.llm_gateway.core import generate_json

    batch_size = cfg.get("gastro", {}).get("batch_size", 10)
    temperature = cfg["llm"]["temperature_subjective"]
    chf_to_eur = cfg["costs"]["chf_to_eur"]

    raw = raw_dir(cfg, "gastro_source")
    all_records: list[dict] = []

    batches = [restaurant_list[i:i + batch_size]
               for i in range(0, len(restaurant_list), batch_size)]

    if limit_batches is not None:
        batches = batches[:limit_batches]

    for batch_idx, batch in enumerate(batches, 1):
        out_path = (Path(raw) / f"gastro_prices_run{run_number}" /
                    f"batch{batch_idx:03d}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            import json
            envelope = json.loads(out_path.read_text(encoding="utf-8"))
            all_records.extend(envelope.get("records", []))
            continue

        batch_list = "\n".join(
            f"- {r.get('restaurant_id', r.get('name', '?'))}: {r.get('name', '?')} "
            f"({r.get('country', '?')}/{r.get('region', '?')})"
            for r in batch
        )

        variables = {
            "batch_list": batch_list,
            "chf_to_eur": chf_to_eur,
        }

        result = generate_json(
            template_id="gastro_prices",
            variables=variables,
            record_schema_id="restaurant_record",
            temperature=temperature,
            out_path=out_path,
            cfg=cfg,
            kind="gastro_prices",
        )

        if result.ok:
            all_records.extend(result.records)
        else:
            logger.warning(f"Run {run_number} batch {batch_idx} failed: {result.error}")

    return all_records


def _build_runs_df(restaurant_list: list[dict], all_runs: dict[int, list[dict]],
                   merge_log: list[dict]) -> pd.DataFrame:
    """Build runs DataFrame from list + price runs, logging rejects."""
    rows = []
    id_lookup = {r.get("restaurant_id", r.get("name", "")): r for r in restaurant_list}

    for run_number, records in sorted(all_runs.items()):
        price_lookup = {}
        for rec in records:
            rid = rec.get("restaurant_id")
            if rid:
                price_lookup[rid] = rec

        for item in restaurant_list:
            rid = item.get("restaurant_id", "")
            base = {
                "restaurant_id": rid,
                "run": run_number,
                "name": item.get("name", ""),
                "country": item.get("country", ""),
                "region": item.get("region", ""),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "elevation_m": item.get("elevation_m"),
                "restaurant_type": item.get("restaurant_type", "restaurant"),
                "ski_area_hint": item.get("ski_area_hint"),
            }

            prices = price_lookup.get(rid, {})
            base["lunch_main_eur"] = prices.get("lunch_main_eur")
            base["lunch_drink_eur"] = prices.get("lunch_drink_eur")
            base["price_level"] = prices.get("price_level")
            base["confidence"] = prices.get("confidence", item.get("confidence"))
            base["reason_price"] = prices.get("reason_price")

            if base["lat"] is None or base["lon"] is None:
                merge_log.append({
                    "batch_id": f"run{run_number}",
                    "item_id": rid,
                    "record_name": base["name"],
                    "reason": "schema_violation",
                    "detail": "Missing lat/lon coordinates",
                })
                continue

            rows.append(base)

    return pd.DataFrame(rows)


def run(cfg: dict, limit_batches: int | None = None, single_run: int | None = None):
    """Full C2 pipeline: fetch restaurants across all regions, run prices, merge."""
    search_regions = cfg.get("gastro", {}).get("search_regions", [])
    n_runs = cfg["llm"]["runs"]
    min_items = cfg.get("gastro", {}).get("min_items", 200)

    all_restaurants: list[dict] = []
    existing_names: list[str] = []
    merge_log: list[dict] = []

    # Phase 1: fetch restaurant lists per region
    for region_entry in search_regions:
        items = fetch_restaurant_list(cfg, region_entry, existing_names, limit_batches)
        for item in items:
            from common.ids import restaurant_id as make_rid
            rid = make_rid(item.get("country", ""), item.get("region", ""),
                           item.get("name", ""))
            item["restaurant_id"] = rid
            existing_names.append(item.get("name", ""))
        all_restaurants.extend(items)

    logger.info(f"Total restaurants listed: {len(all_restaurants)}")

    # Phase 2: fetch prices in runs
    runs_to_do = [single_run] if single_run else list(range(1, n_runs + 1))
    all_runs: dict[int, list[dict]] = {}

    for run_number in runs_to_do:
        records = fetch_restaurant_prices(all_restaurants, cfg, run_number, limit_batches)
        all_runs[run_number] = records
        logger.info(f"Run {run_number}: {len(records)} price records")

    # Build runs DataFrame
    runs_df = _build_runs_df(all_restaurants, all_runs, merge_log)

    if runs_df.empty:
        logger.error("No valid restaurant data collected")
        sys.exit(3)

    # Merge runs
    from common.contract_io import write_csv
    proc = processed_dir(cfg)
    Path(proc).mkdir(parents=True, exist_ok=True)

    # Write runs
    write_csv(runs_df, Path(proc) / "restaurants_runs.csv", "restaurant_runs",
              "gastro_source@1.0.0")

    # Merge to final
    merged = merge_restaurant_runs(runs_df)

    if len(merged) < min_items and limit_batches is None:
        logger.error(f"Only {len(merged)} restaurants, need {min_items}")
        sys.exit(3)

    write_csv(merged, Path(proc) / "restaurants.csv", "restaurant_table",
              "gastro_source@1.0.0")

    # Write merge log
    if merge_log:
        log_df = pd.DataFrame(merge_log)
        write_csv(log_df, Path(proc) / "restaurants_merge_log.csv", "merge_log",
                  "gastro_source@1.0.0")

    logger.info(f"Wrote {len(merged)} restaurants to restaurants.csv")
