"""Fetch ski resort list from OpenSkiData (openskidata.org)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import requests

from common.ids import resort_id, slugify
from common.log import get_logger
from common.paths import raw_dir

logger = get_logger("resort_source.osm")

OPENSKIDATA_URL = "https://tiles.openskimap.org/geojson/ski_areas.geojson"

EXCLUDE_PATTERNS = [
    "schanze", "stadion", "loipe", "langlauf", "biathlon",
    "sprungschanze", "nordisch", "cross-country", "skisprung",
    "skispringen", "fond", "skating",
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_excluded(name: str) -> bool:
    low = name.lower()
    return any(p in low for p in EXCLUDE_PATTERNS)


def _extract_resorts(data: dict, countries: list[str]) -> list[dict]:
    """Extract resort records from OpenSkiData GeoJSON."""
    country_set = set(countries)
    resorts = []

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        name = props.get("name")
        if not name or _is_excluded(name):
            continue

        activities = props.get("activities") or []
        if "downhill" not in activities:
            continue

        if props.get("status") not in ("operating", None):
            continue

        places = props.get("places", [])
        country = None
        region = ""
        for p in places:
            iso = p.get("iso3166_2", "")
            c = iso.split("-")[0] if iso else ""
            if c in country_set:
                country = c
                loc = p.get("localized", {}).get("en", {}) or p.get("localized", {}).get("de", {}) or {}
                region = loc.get("region", "")
                break

        if not country:
            continue

        geom = feature.get("geometry", {})
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type == "Point" and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        elif geom_type == "Polygon" and coords:
            ring = coords[0]
            lon = sum(c[0] for c in ring) / len(ring)
            lat = sum(c[1] for c in ring) / len(ring)
        elif geom_type == "MultiPolygon" and coords:
            ring = coords[0][0]
            lon = sum(c[0] for c in ring) / len(ring)
            lat = sum(c[1] for c in ring) / len(ring)
        else:
            continue

        if lat < 43 or lat > 49 or lon < 4 or lon > 17:
            continue

        stats = props.get("statistics", {})
        runs_data = stats.get("runs", {}).get("byActivity", {}).get("downhill", {}).get("byDifficulty", {})
        slope_km = sum(d.get("lengthInKm", 0) for d in runs_data.values()) if isinstance(runs_data, dict) else 0

        max_elev = stats.get("maxElevation")
        min_elev = stats.get("minElevation")
        lifts_by_type = stats.get("lifts", {}).get("byType", {})
        lift_count = sum(
            t.get("count", 0) for t in lifts_by_type.values()
            if isinstance(t, dict)
        )

        if lift_count == 0:
            continue

        easy_cats = ("easy", "novice")
        inter_cats = ("intermediate",)
        adv_cats = ("advanced", "expert", "freeride", "extreme")
        n_runs_easy = sum(runs_data.get(c, {}).get("count", 0) for c in easy_cats)
        n_runs_intermediate = sum(runs_data.get(c, {}).get("count", 0) for c in inter_cats)
        n_runs_advanced = sum(runs_data.get(c, {}).get("count", 0) for c in adv_cats)
        km_easy = round(sum(runs_data.get(c, {}).get("lengthInKm", 0) for c in easy_cats), 1)
        km_intermediate = round(sum(runs_data.get(c, {}).get("lengthInKm", 0) for c in inter_cats), 1)
        km_advanced = round(sum(runs_data.get(c, {}).get("lengthInKm", 0) for c in adv_cats), 1)

        websites = props.get("websites") or []
        sources = props.get("sources") or []

        rec = {
            "name": name,
            "country": country,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "openskidata_id": props.get("id", ""),
            "website": websites[0] if websites else None,
            "region": region,
            "slope_km": round(slope_km, 1) if slope_km > 0 else None,
            "top_elevation_m": round(max_elev, 0) if max_elev is not None else None,
            "base_elevation_m": round(min_elev, 0) if min_elev is not None else None,
            "lift_count": lift_count,
            "n_runs_easy": n_runs_easy or None,
            "n_runs_intermediate": n_runs_intermediate or None,
            "n_runs_advanced": n_runs_advanced or None,
            "km_easy": km_easy or None,
            "km_intermediate": km_intermediate or None,
            "km_advanced": km_advanced or None,
            "sources": sources,
        }
        resorts.append(rec)

    return resorts


def _dedup_resorts(resorts: list[dict], radius_km: float = 5.0) -> list[dict]:
    """Remove duplicates (same normalized name within radius)."""
    kept: list[dict] = []
    for r in resorts:
        is_dup = False
        norm = slugify(r["name"])
        for k in kept:
            if slugify(k["name"]) == norm:
                dist = _haversine_km(r["lat"], r["lon"], k["lat"], k["lon"])
                if dist < radius_km:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(r)
    return kept


def fetch_osm_resorts(cfg: dict) -> list[dict]:
    """Fetch ski resorts from OpenSkiData for all configured countries.

    Downloads ski_areas.geojson once and caches it locally.
    Returns list of dicts with: name, country, lat, lon, website, region,
    slope_km, top_elevation_m, base_elevation_m, lift_count.
    """
    countries = cfg["resorts"]["countries"]
    raw = raw_dir(cfg, "resort_source")
    cache_dir = raw / "openskidata"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "ski_areas.geojson"

    if cache_path.exists():
        logger.info("OpenSkiData cache hit: %s", cache_path)
        data = json.loads(cache_path.read_text("utf-8"))
    else:
        logger.info("Downloading OpenSkiData ski_areas.geojson ...")
        resp = requests.get(OPENSKIDATA_URL, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        cache_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        logger.info("Cached %d features", len(data.get("features", [])))

    resorts = _extract_resorts(data, countries)
    logger.info("Extracted %d alpine downhill resorts for %s", len(resorts), countries)

    by_country = {}
    for r in resorts:
        by_country.setdefault(r["country"], []).append(r)
    for c in sorted(by_country):
        logger.info("  %s: %d resorts", c, len(by_country[c]))

    deduped = _dedup_resorts(resorts)
    logger.info("After dedup: %d resorts (from %d)", len(deduped), len(resorts))

    seen_ids: dict[str, int] = {}
    for r in deduped:
        rid = resort_id(r["country"], r["name"])
        if rid in seen_ids:
            seen_ids[rid] += 1
            rid = f"{rid}-{seen_ids[rid]}"
        else:
            seen_ids[rid] = 1
        r["resort_id"] = rid

    return deduped
