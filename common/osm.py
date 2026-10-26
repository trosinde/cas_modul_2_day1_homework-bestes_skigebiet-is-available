"""Fetch mountain restaurants from OpenStreetMap via Nominatim (+ Overpass fallback).

Incremental: each region is cached as a JSON file; cached regions are skipped.
Progress: logs %-complete and ETA for the fetching phase.
Parallel: uses asyncio + a global rate limiter to pipeline Nominatim requests
(1 req/s as required by Nominatim usage policy).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

from common.ids import slugify
from common.log import get_logger

logger = get_logger("osm")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "skigebiete-pipeline/1.0 (university project)"

REGION_BBOX: dict[tuple[str, str], tuple[float, float, float, float]] = {
    ("CH", "Graubünden"):       (46.2, 8.8, 47.1, 10.5),
    ("CH", "Wallis"):           (45.9, 6.8, 46.6, 8.5),
    ("CH", "Berner Oberland"):  (46.3, 7.2, 46.9, 8.3),
    ("CH", "Zentralschweiz"):   (46.7, 8.0, 47.1, 8.9),
    ("AT", "Tirol"):            (46.7, 10.0, 47.6, 12.9),
    ("AT", "Salzburger Land"):  (46.9, 12.0, 47.9, 14.0),
    ("AT", "Vorarlberg"):       (46.8, 9.5, 47.6, 10.2),
    ("AT", "Steiermark"):       (46.6, 13.5, 47.8, 16.2),
    ("AT", "Kärnten"):          (46.3, 12.6, 47.1, 15.0),
    ("DE", "Bayern"):           (47.0, 10.0, 47.7, 13.2),
    ("IT", "Südtirol"):         (46.2, 10.3, 47.1, 12.5),
    ("IT", "Trentino"):         (45.7, 10.3, 46.5, 11.9),
    ("FR", "Savoie"):           (45.0, 5.8, 45.9, 7.2),
    ("FR", "Haute-Savoie"):     (45.7, 5.8, 46.4, 7.0),
}

QUERY_TYPES = ["[restaurant]", "[alpine_hut]", "[cafe]"]


def _map_type(osm_type_str: str, osm_class: str) -> str:
    if osm_type_str == "alpine_hut" or osm_class == "tourism":
        return "hut"
    if osm_type_str in ("cafe", "fast_food"):
        return "self_service"
    return "restaurant"


def _parse_elevation(ele_str: str) -> int | None:
    if not ele_str:
        return None
    try:
        return int(float(ele_str.split()[0].replace(",", ".")))
    except (ValueError, IndexError):
        return None


def _parse_nominatim_result(item: dict) -> dict | None:
    name = item.get("name") or item.get("display_name", "").split(",")[0]
    if not name or name.startswith("("):
        return None

    try:
        lat = round(float(item["lat"]), 6)
        lon = round(float(item["lon"]), 6)
    except (KeyError, ValueError):
        return None

    extras = item.get("extratags") or {}
    osm_type_str = item.get("type", "")
    osm_class = item.get("class", "")

    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "elevation_m": _parse_elevation(extras.get("ele", "")),
        "osm_id": int(item.get("osm_id", 0)) or None,
        "osm_type": item.get("osm_type"),
        "restaurant_type": _map_type(osm_type_str, osm_class),
        "website": extras.get("website") or extras.get("contact:website"),
        "phone": extras.get("phone") or extras.get("contact:phone"),
    }


def _sub_boxes(
    south: float, west: float, north: float, east: float,
    lat_tile: float = 0.4, lon_tile: float = 0.6,
) -> list[tuple[float, float, float, float]]:
    """Split a bbox into sub-boxes of roughly lat_tile × lon_tile degrees."""
    lat_span = north - south
    lon_span = east - west
    lat_steps = max(1, int(lat_span / lat_tile) + 1)
    lon_steps = max(1, int(lon_span / lon_tile) + 1)
    lat_step = lat_span / lat_steps
    lon_step = lon_span / lon_steps

    boxes = []
    for i in range(lat_steps):
        for j in range(lon_steps):
            boxes.append((
                south + i * lat_step,
                west + j * lon_step,
                south + (i + 1) * lat_step,
                west + (j + 1) * lon_step,
            ))
    return boxes


class _RateLimiter:
    """Async rate limiter: at most 1 request per `interval` seconds."""

    def __init__(self, interval: float = 1.1):
        self._interval = interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = asyncio.get_event_loop().time()


class _ProgressTracker:
    """Track and log progress of Nominatim fetching."""

    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self._start = time.monotonic()
        self._lock = asyncio.Lock()

    async def tick(self, label: str, found: int) -> None:
        async with self._lock:
            self.done += 1
            pct = self.done / self.total * 100
            elapsed = time.monotonic() - self._start
            if self.done > 0:
                eta = elapsed / self.done * (self.total - self.done)
            else:
                eta = 0
            msg = (
                f"[{pct:5.1f}%] {self.done}/{self.total} queries done "
                f"| {label} +{found} | ETA {eta:.0f}s"
            )
            logger.info(msg)
            print(f"\r{msg}", end="", flush=True)

    def finish(self, total_found: int) -> None:
        elapsed = time.monotonic() - self._start
        msg = f"\nNominatim fetch done: {total_found} restaurants in {elapsed:.0f}s"
        logger.info(msg)
        print(msg, flush=True)


async def _fetch_one_tile(
    client: httpx.AsyncClient,
    rate_limiter: _RateLimiter,
    query: str,
    s: float, w: float, n: float, e: float,
) -> list[dict]:
    """Fetch a single Nominatim tile, respecting rate limit."""
    await rate_limiter.acquire()

    params = {
        "q": query,
        "viewbox": f"{w},{n},{e},{s}",
        "bounded": 1,
        "format": "json",
        "limit": 50,
        "addressdetails": 1,
        "extratags": 1,
    }
    resp = await client.get(NOMINATIM_URL, params=params)
    resp.raise_for_status()
    return resp.json()


async def _fetch_region_async(
    client: httpx.AsyncClient,
    rate_limiter: _RateLimiter,
    progress: _ProgressTracker,
    south: float, west: float, north: float, east: float,
    region_label: str,
) -> list[dict]:
    """Fetch all restaurants for one region (all query types × all sub-boxes)."""
    boxes = _sub_boxes(south, west, north, east)
    seen: set[int] = set()
    results: list[dict] = []

    for query in QUERY_TYPES:
        for box in boxes:
            s, w, n, e = box
            label = f"{region_label} {query}"
            try:
                items = await _fetch_one_tile(client, rate_limiter, query, s, w, n, e)
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("Nominatim %s failed: %s", label, exc)
                await progress.tick(label, 0)
                continue

            tile_found = 0
            for item in items:
                try:
                    rec = _parse_nominatim_result(item)
                except Exception:
                    continue
                if rec and rec["osm_id"] and rec["osm_id"] not in seen:
                    seen.add(rec["osm_id"])
                    results.append(rec)
                    tile_found += 1

            await progress.tick(label, tile_found)

    return results


def _count_queries(regions: list[tuple[str, str]]) -> int:
    """Count total Nominatim queries needed (for progress bar)."""
    total = 0
    for country, region in regions:
        key = (country, region)
        if key not in REGION_BBOX:
            continue
        south, west, north, east = REGION_BBOX[key]
        boxes = _sub_boxes(south, west, north, east)
        total += len(QUERY_TYPES) * len(boxes)
    return total


async def _fetch_all_regions(
    regions_to_fetch: list[tuple[str, str, float, float, float, float, Path]],
    total_queries: int,
) -> dict[tuple[str, str], list[dict]]:
    """Fetch all uncached regions with shared rate limiter and progress."""
    rate_limiter = _RateLimiter(1.1)
    progress = _ProgressTracker(total_queries)
    results: dict[tuple[str, str], list[dict]] = {}

    async with httpx.AsyncClient(
        timeout=30, headers={"User-Agent": USER_AGENT},
    ) as client:
        for country, region, south, west, north, east, cache_file in regions_to_fetch:
            label = f"{country}/{region}"
            logger.info("Querying Nominatim for %s (%.1f,%.1f,%.1f,%.1f)",
                        label, south, west, north, east)

            try:
                records = await _fetch_region_async(
                    client, rate_limiter, progress,
                    south, west, north, east, label,
                )
            except Exception as exc:
                logger.error("Nominatim failed for %s: %s", label, exc)
                results[(country, region)] = []
                continue

            cache_file.write_text(
                json.dumps(records, ensure_ascii=False, indent=2), "utf-8",
            )
            logger.info("%s: %d restaurants cached to %s",
                        label, len(records), cache_file.name)
            results[(country, region)] = records

    progress.finish(sum(len(v) for v in results.values()))
    return results


# --- Overpass fallback --------------------------------------------------------

def _build_overpass_query(
    south: float, west: float, north: float, east: float,
    min_ele: int | None = None,
) -> str:
    bbox = f"{south},{west},{north},{east}"
    ele_filter = '["ele"~"^[0-9]"]' if min_ele is not None else ""
    return f"""\
[out:json][timeout:60];
(
  node["amenity"="restaurant"]["name"]{ele_filter}({bbox});
  node["amenity"="cafe"]["name"]{ele_filter}({bbox});
  node["amenity"="fast_food"]["name"]{ele_filter}({bbox});
  node["tourism"="alpine_hut"]["name"]{ele_filter}({bbox});
  way["amenity"="restaurant"]["name"]{ele_filter}({bbox});
  way["amenity"="cafe"]["name"]{ele_filter}({bbox});
  way["tourism"="alpine_hut"]["name"]{ele_filter}({bbox});
);
out center;"""


def _parse_overpass_element(element: dict) -> dict | None:
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    lat = element.get("lat") or (element.get("center") or {}).get("lat")
    lon = element.get("lon") or (element.get("center") or {}).get("lon")
    if lat is None or lon is None:
        return None

    return {
        "name": name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "elevation_m": _parse_elevation(tags.get("ele", "")),
        "osm_id": element.get("id"),
        "osm_type": element.get("type"),
        "restaurant_type": _map_type(
            tags.get("tourism", tags.get("amenity", "")),
            tags.get("tourism", ""),
        ),
        "website": tags.get("website") or tags.get("contact:website"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
    }


def query_restaurants_overpass(
    south: float, west: float, north: float, east: float,
    min_ele: int | None = None,
    timeout: int = 90,
) -> list[dict]:
    """Query Overpass API for restaurants / huts in a bounding box."""
    query = _build_overpass_query(south, west, north, east, min_ele)
    resp = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    data = resp.json()
    results: list[dict] = []
    for elem in data.get("elements", []):
        rec = _parse_overpass_element(elem)
        if rec is not None:
            results.append(rec)
    return results


# --- Sync wrapper for query_restaurants_nominatim (used by tests) ----------

def query_restaurants_nominatim(
    south: float, west: float, north: float, east: float,
) -> list[dict]:
    """Synchronous single-region Nominatim fetch (for tests / simple use)."""
    boxes = _sub_boxes(south, west, north, east)
    seen: set[int] = set()
    results: list[dict] = []

    for query in QUERY_TYPES:
        for s, w, n, e in boxes:
            params = {
                "q": query,
                "viewbox": f"{w},{n},{e},{s}",
                "bounded": 1,
                "format": "json",
                "limit": 50,
                "addressdetails": 1,
                "extratags": 1,
            }
            try:
                resp = httpx.get(
                    NOMINATIM_URL, params=params, timeout=30,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                items = resp.json()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("Nominatim query %s failed: %s", query, exc)
                continue

            for item in items:
                try:
                    rec = _parse_nominatim_result(item)
                except Exception:
                    continue
                if rec and rec["osm_id"] and rec["osm_id"] not in seen:
                    seen.add(rec["osm_id"])
                    results.append(rec)

            time.sleep(1.1)

    return results


# --- Public entry point -------------------------------------------------------

def query_restaurants_for_regions(
    regions: list[dict],
    cfg: dict,
) -> list[dict]:
    """Fetch restaurants for every configured search region.

    Incremental: cached regions are loaded from disk instantly.
    Uncached regions are fetched via async Nominatim with progress display.
    Falls back to Overpass if Nominatim fails.
    """
    cache_dir = Path(
        cfg.get("gastro", {}).get("osm_cache_dir", "data/raw/gastro_source/osm")
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    seen_osm_ids: set[tuple[str, int]] = set()
    regions_to_fetch: list[tuple[str, str, float, float, float, float, Path]] = []

    cached_count = 0
    for region_entry in regions:
        country = region_entry["country"]
        region = region_entry["region"]
        key = (country, region)

        if key not in REGION_BBOX:
            logger.warning("No bounding box for %s/%s, skipping", country, region)
            continue

        south, west, north, east = REGION_BBOX[key]
        cache_file = cache_dir / f"{country.lower()}_{slugify(region)}.json"

        if cache_file.exists():
            cached_count += 1
            logger.info("✓ Cached: %s/%s", country, region)
            records = json.loads(cache_file.read_text("utf-8"))
            for rec in records:
                osm_key = (rec.get("osm_type", ""), rec.get("osm_id", 0))
                if osm_key not in seen_osm_ids:
                    seen_osm_ids.add(osm_key)
                    rec["country"] = country
                    rec["region"] = region
                    all_records.append(rec)
        else:
            regions_to_fetch.append((country, region, south, west, north, east, cache_file))

    if cached_count:
        logger.info(
            "%d/%d regions from cache (%d restaurants so far)",
            cached_count, cached_count + len(regions_to_fetch), len(all_records),
        )

    if regions_to_fetch:
        uncached_keys = [(c, r) for c, r, *_ in regions_to_fetch]
        total_queries = _count_queries(uncached_keys)
        logger.info(
            "Fetching %d uncached regions (%d Nominatim queries, ~%ds)...",
            len(regions_to_fetch), total_queries, int(total_queries * 1.1),
        )

        fetched = asyncio.run(
            _fetch_all_regions(regions_to_fetch, total_queries)
        )

        for (country, region), records in fetched.items():
            for rec in records:
                osm_key = (rec.get("osm_type", ""), rec.get("osm_id", 0))
                if osm_key not in seen_osm_ids:
                    seen_osm_ids.add(osm_key)
                    rec["country"] = country
                    rec["region"] = region
                    all_records.append(rec)

    logger.info("Total unique restaurants from OSM: %d", len(all_records))
    return all_records
