"""Fetch real driving distances and times from OSRM."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import requests

from common.log import get_logger
from common.paths import raw_dir

logger = get_logger("resort_source.routing")

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"


def _fetch_route(origin: dict, resort: dict, session: requests.Session) -> tuple[str, dict]:
    """Fetch a single route from OSRM. Returns (resort_id, result_dict)."""
    url = OSRM_URL.format(
        lon1=origin["lon"], lat1=origin["lat"],
        lon2=resort["lon"], lat2=resort["lat"],
    )
    rid = resort["resort_id"]
    try:
        resp = session.get(url, params={"overview": "false"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return rid, {"drive_distance_km": None, "drive_time_min": None}
        route = data["routes"][0]
        return rid, {
            "drive_distance_km": round(route["distance"] / 1000, 1),
            "drive_time_min": round(route["duration"] / 60, 0),
        }
    except Exception as e:
        logger.warning("OSRM error for %s: %s", rid, e)
        return rid, {"drive_distance_km": None, "drive_time_min": None}


def fetch_routes(resorts: list[dict], cfg: dict) -> dict[str, dict]:
    """Fetch driving routes from origin to all resorts (parallel, incremental).

    Returns dict mapping resort_id -> {drive_distance_km, drive_time_min}.
    Results are cached in data/raw/resort_source/osrm/routes.json.
    """
    origin = cfg["origin"]
    raw = raw_dir(cfg, "resort_source")
    cache_path = raw / "osrm" / "routes.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache: dict[str, dict] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text("utf-8"))

    missing = [r for r in resorts if r["resort_id"] not in cache]
    total = len(resorts)
    cached = total - len(missing)

    if not missing:
        logger.info("OSRM: all %d routes cached", total)
        return cache

    logger.info("OSRM: %d to fetch, %d cached, %d total", len(missing), cached, total)

    by_country: dict[str, list[dict]] = {}
    for r in missing:
        by_country.setdefault(r.get("country", "??"), []).append(r)

    lock = Lock()
    done_count = 0
    done_by_country: dict[str, int] = {c: 0 for c in by_country}
    total_by_country: dict[str, int] = {c: len(rs) for c, rs in by_country.items()}

    def _progress():
        parts = []
        for c in sorted(total_by_country):
            d = done_by_country[c]
            t = total_by_country[c]
            pct = d / t * 100 if t else 100
            parts.append(f"{c}:{d}/{t}({pct:.0f}%)")
        bar_total = len(missing)
        bar_done = done_count
        pct_all = bar_done / bar_total * 100 if bar_total else 100
        sys.stderr.write(f"\r  OSRM: {bar_done}/{bar_total} ({pct_all:.0f}%) [{' '.join(parts)}]   ")
        sys.stderr.flush()

    max_workers = min(8, len(missing))
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_fetch_route, origin, r, session): r
                for r in missing
            }
            for future in as_completed(futures):
                resort = futures[future]
                rid, result = future.result()
                with lock:
                    cache[rid] = result
                    done_count += 1
                    c = resort.get("country", "??")
                    done_by_country[c] = done_by_country.get(c, 0) + 1
                    _progress()
                    if done_count % 50 == 0:
                        cache_path.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")

    cache_path.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")
    sys.stderr.write(f"\r  OSRM: {len(missing)} routes fetched, {len(cache)} total" + " " * 30 + "\n")
    sys.stderr.flush()

    return cache
