"""C2: Fetch mountain restaurant data from OSM, extract menu prices."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

from common.ids import restaurant_id as make_rid
from common.log import get_logger
from common.paths import raw_dir, processed_dir

logger = get_logger("gastro_source")

MOCK_RESTAURANTS = [
    {"name": "Bergrestaurant Sonnalp", "country": "CH", "region": "Graubünden",
     "lat": 46.8, "lon": 9.8, "elevation_m": 2100, "restaurant_type": "restaurant",
     "osm_id": 100001, "osm_type": "node", "website": None},
    {"name": "Alphütte Matterblick", "country": "CH", "region": "Wallis",
     "lat": 46.02, "lon": 7.75, "elevation_m": 2300, "restaurant_type": "hut",
     "osm_id": 100002, "osm_type": "node", "website": None},
    {"name": "Jausenstation Alpenrose", "country": "AT", "region": "Tirol",
     "lat": 47.1, "lon": 11.3, "elevation_m": 1800, "restaurant_type": "restaurant",
     "osm_id": 100003, "osm_type": "node", "website": None},
    {"name": "Berggasthof Edelweiss", "country": "AT", "region": "Salzburger Land",
     "lat": 47.3, "lon": 13.1, "elevation_m": 1600, "restaurant_type": "restaurant",
     "osm_id": 100004, "osm_type": "node", "website": None},
    {"name": "Almwirtschaft Panorama", "country": "DE", "region": "Bayern",
     "lat": 47.4, "lon": 11.1, "elevation_m": 1500, "restaurant_type": "restaurant",
     "osm_id": 100005, "osm_type": "node", "website": None},
    {"name": "Rifugio Monte Sole", "country": "IT", "region": "Südtirol",
     "lat": 46.6, "lon": 11.4, "elevation_m": 1900, "restaurant_type": "hut",
     "osm_id": 100006, "osm_type": "node", "website": None},
    {"name": "Malga Ciapela", "country": "IT", "region": "Trentino",
     "lat": 46.1, "lon": 11.7, "elevation_m": 1450, "restaurant_type": "restaurant",
     "osm_id": 100007, "osm_type": "node", "website": None},
    {"name": "Chalet Les Marmottes", "country": "FR", "region": "Savoie",
     "lat": 45.5, "lon": 6.5, "elevation_m": 1700, "restaurant_type": "restaurant",
     "osm_id": 100008, "osm_type": "node", "website": None},
]


def _restaurant_row(rec: dict) -> dict:
    """Create a full restaurant row dict with all schema fields initialised."""
    return {
        "name": rec["name"],
        "country": rec["country"],
        "region": rec["region"],
        "lat": rec["lat"],
        "lon": rec["lon"],
        "elevation_m": rec.get("elevation_m"),
        "restaurant_type": rec.get("restaurant_type", "restaurant"),
        "ski_area_hint": None,
        "osm_id": rec.get("osm_id"),
        "osm_type": rec.get("osm_type"),
        "website": rec.get("website"),
        "lunch_main_eur": None,
        "lunch_drink_eur": None,
        "price_source": None,
        "is_estimate": None,
        "menu_url": None,
        "price_source_detail": None,
        "price_level": None,
        "confidence": None,
        "reason_price": None,
    }


def _compute_lunch_price(items: list[dict]) -> float | None:
    """Average of the lower (cheaper) half of main-course prices.

    Sort expensive -> cheap, take items[len//2:], return mean.
    """
    prices = sorted(
        [it["price_eur"] for it in items
         if it.get("price_eur") is not None and it["price_eur"] > 0],
        reverse=True,
    )
    if not prices:
        return None
    lower_half = prices[len(prices) // 2:]
    if not lower_half:
        return prices[-1]
    return round(sum(lower_half) / len(lower_half), 2)


def _apply_country_fallback(row: dict, cfg: dict) -> None:
    """Set lunch prices from the country-level statistical estimate."""
    country = row["country"]
    avg_prices = cfg.get("gastro", {}).get("country_avg_prices", {})
    country_data = avg_prices.get(country, {})

    if isinstance(country_data, dict) and "lunch_main_eur" in country_data:
        row["lunch_main_eur"] = country_data["lunch_main_eur"]
        row["lunch_drink_eur"] = country_data.get("lunch_drink_eur")
        row["price_source"] = "country_statistics_estimate"
        row["is_estimate"] = True
        row["price_source_detail"] = avg_prices.get("source", "Eurostat")


def _load_cached_extraction(out_path: Path) -> dict | None:
    """Load a previously successful menu extraction from its envelope file.

    Returns the parsed data dict if the file exists and represents a
    successful extraction (error is None, raw_response parses as JSON).
    Returns None otherwise (file missing, error envelope, corrupt file).
    """
    if not out_path.exists():
        return None
    try:
        envelope = json.loads(out_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if envelope.get("error") is not None:
        return None
    raw = envelope.get("raw_response", "")
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _extract_prices(restaurants: list[dict], cfg: dict, total_all: int = 0) -> None:
    """Extract prices from menus (Playwright + LLM) for restaurants with website.

    Rows already have country fallback prices; this upgrades them to real
    menu prices where a Speisekarte is found.
    """
    from common.menu_scraper import find_menu_page
    from components.llm_gateway.core import extract_json

    menu_cache = Path(
        cfg.get("gastro", {}).get("menu_cache_dir", "data/raw/gastro_source/menus")
    )
    menu_cache.mkdir(parents=True, exist_ok=True)

    chf_to_eur = cfg["costs"]["chf_to_eur"]
    temperature = cfg["llm"]["temperature_factual"]
    raw = raw_dir(cfg, "gastro_source")

    total = len(restaurants)
    n_menu = 0
    n_cached = 0
    n_no_menu = 0
    n_error = 0
    t0 = time.monotonic()

    for i, row in enumerate(restaurants, 1):
        name = row.get("name", "?")
        website = row.get("website", "")
        elapsed = time.monotonic() - t0
        eta = elapsed / i * (total - i) if i > 0 else 0

        print(
            f"\r[{i/total*100:5.1f}%] {i}/{total} mit Website | "
            f"{total_all} gesamt | "
            f"menu:{n_menu} cached:{n_cached} fallback:{n_no_menu} err:{n_error} | "
            f"ETA {eta:.0f}s | {name[:40]}",
            end="", flush=True,
        )

        try:
            menu_result = find_menu_page(website, cache_dir=menu_cache)
        except Exception as exc:
            logger.warning("Scrape failed for %s (%s): %s", name, website, exc)
            n_error += 1
            continue

        if not menu_result.found:
            n_no_menu += 1
            continue

        text = menu_result.menu_text or menu_result.menu_html or ""
        if not text.strip():
            n_no_menu += 1
            continue

        if len(text) > 15_000:
            text = text[:15_000]

        out_path = (
            Path(raw) / "menu_extractions" / f"{row['restaurant_id']}.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cached_data = _load_cached_extraction(out_path)
        if cached_data is not None:
            if cached_data.get("items"):
                price = _compute_lunch_price(cached_data["items"])
                if price is not None:
                    row["lunch_main_eur"] = price
                    row["lunch_drink_eur"] = cached_data.get("drink_05l_eur")
                    row["price_source"] = "menu_card"
                    row["is_estimate"] = False
                    row["menu_url"] = menu_result.menu_url
                    row["price_source_detail"] = f"Menu: {menu_result.menu_url}"
                    n_menu += 1
                    n_cached += 1
                    continue
            n_no_menu += 1
            n_cached += 1
            continue

        try:
            data = extract_json(
                template_id="gastro_menu_extract",
                variables={"menu_text": text, "chf_to_eur": chf_to_eur},
                temperature=temperature,
                out_path=out_path,
                cfg=cfg,
                kind="gastro_menu_extract",
            )
        except Exception as exc:
            logger.warning("LLM extraction failed for %s: %s", name, exc)
            n_error += 1
            continue

        if data and data.get("items"):
            price = _compute_lunch_price(data["items"])
            if price is not None:
                row["lunch_main_eur"] = price
                row["lunch_drink_eur"] = data.get("drink_05l_eur")
                row["price_source"] = "menu_card"
                row["is_estimate"] = False
                row["menu_url"] = menu_result.menu_url
                row["price_source_detail"] = f"Menu: {menu_result.menu_url}"
                n_menu += 1
                continue

        n_no_menu += 1

    elapsed = time.monotonic() - t0
    print(
        f"\nMenu extraction done: {n_menu} from menu ({n_cached} cached), "
        f"{n_no_menu} no menu found, {n_error} errors | "
        f"{total} mit Website von {total_all} gesamt "
        f"({elapsed:.0f}s)",
        flush=True,
    )
    logger.info(
        "Prices: %d from menu, %d no menu, %d errors (%.0fs)",
        n_menu, n_no_menu, n_error, elapsed,
    )


def run(cfg: dict, limit_batches: int | None = None, menu_limit: int | None = None):
    """C2 pipeline: fetch restaurants from OSM, extract prices from menus."""
    provider = cfg.get("llm", {}).get("provider", "auto")
    is_mock = provider == "mock"
    min_items = cfg.get("gastro", {}).get("min_items", 200)

    # --- Phase 1: restaurant list -------------------------------------------
    if is_mock:
        raw_restaurants = list(MOCK_RESTAURANTS)
        logger.info("Mock mode: using %d synthetic restaurants", len(raw_restaurants))
    else:
        from common.osm import query_restaurants_for_regions
        regions = cfg.get("gastro", {}).get("search_regions", [])
        raw_restaurants = query_restaurants_for_regions(regions, cfg)

    # Build full rows and assign IDs, deduplicating by restaurant_id
    restaurants: list[dict] = []
    seen_ids: set[str] = set()

    for rec in raw_restaurants:
        row = _restaurant_row(rec)
        rid = make_rid(row["country"], row["region"], row["name"])
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        row["restaurant_id"] = rid
        restaurants.append(row)

    if limit_batches is not None:
        batch_size = cfg.get("gastro", {}).get("batch_size", 10)
        restaurants = restaurants[: limit_batches * batch_size]

    logger.info("Total restaurants: %d", len(restaurants))

    # --- Phase 2: prices ----------------------------------------------------
    for row in restaurants:
        _apply_country_fallback(row, cfg)

    scrape_menus = cfg.get("gastro", {}).get("scrape_menus", False)

    if scrape_menus and not is_mock:
        with_website = [r for r in restaurants if r.get("website")]
        if with_website:
            targets = with_website[:menu_limit] if menu_limit else with_website
            logger.info(
                "Menu extraction: %d restaurants with website%s",
                len(targets),
                f" (limited to {menu_limit})" if menu_limit else "",
            )
            _extract_prices(targets, cfg, total_all=len(restaurants))
        else:
            logger.info("No restaurants with website — all use country fallback")
    elif not scrape_menus:
        logger.info("Menu scraping disabled (gastro.scrape_menus=false) — using country fallback only")
        n_countries = len(set(r["country"] for r in restaurants))
        print(f"  {len(restaurants)} Restaurants | Fallback-Preise für {n_countries} Länder")

    if not restaurants:
        logger.error("No restaurants collected")
        sys.exit(3)

    # --- Write output -------------------------------------------------------
    from common.contract_io import write_csv

    proc = processed_dir(cfg)
    Path(proc).mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(restaurants)

    if len(df) < min_items and limit_batches is None:
        logger.warning("Only %d restaurants, target was %d", len(df), min_items)

    write_csv(
        df,
        Path(proc) / "restaurants.csv",
        "restaurant_table",
        "gastro_source@1.0.0",
    )

    logger.info("Wrote %d restaurants to restaurants.csv", len(df))
