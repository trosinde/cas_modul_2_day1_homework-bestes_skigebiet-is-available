"""Scrape ski resort prices from skiresort.de via Playwright (parallel, incremental)."""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
from pathlib import Path
from threading import Lock, Thread

import pandas as pd

from common.ids import slugify
from common.log import get_logger
from common.paths import raw_dir

logger = get_logger("resort_source.scraper")

BASE_URL = "https://www.skiresort.de"


def _make_slug(name: str) -> str:
    slug = slugify(name)
    slug = slug.replace("st-", "st-").replace("--", "-")
    return slug


def _try_slugs(name: str) -> list[str]:
    base = _make_slug(name)
    candidates = [base]
    parts = name.split("/")
    if len(parts) > 1:
        for part in parts:
            candidates.append(_make_slug(part.strip()))
    parts = name.split(" - ")
    if len(parts) > 1:
        candidates.append(_make_slug(parts[0].strip()))
    if "(" in name:
        without_parens = re.sub(r"\s*\(.*?\)", "", name).strip()
        candidates.append(_make_slug(without_parens))
    return list(dict.fromkeys(candidates))


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    text = text.strip().replace("\xa0", " ")
    m = re.search(r"(\d+)[.,](\d+)", text)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"(\d+)[.,][-–—]", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)", text)
    if m:
        return float(m.group(1))
    return None


def _detect_currency(text: str) -> str:
    if "CHF" in text or "Fr." in text:
        return "CHF"
    return "EUR"


def _scrape_resort(page, slug: str, chf_to_eur: float) -> dict:
    """Scrape prices from the resort overview page on skiresort.de."""
    result = {
        "slug": slug,
        "status": "error",
        "source_url": None,
        "day_pass_adult_eur": None,
        "day_pass_youth16_eur": None,
        "day_pass_child13_eur": None,
        "family_pass_eur": None,
        "age_category_16": None,
        "age_category_13": None,
        "family_pass_conditions": None,
        "slope_km": None,
        "top_elevation_m": None,
        "base_elevation_m": None,
        "currency": None,
        "error": None,
    }

    overview_url = f"{BASE_URL}/skigebiet/{slug}/"

    try:
        resp = page.goto(overview_url, wait_until="domcontentloaded", timeout=20000)
        if resp and resp.status == 404:
            result["status"] = "not_found"
            result["error"] = f"404 at {overview_url}"
            return result
        page.wait_for_timeout(2000)

        title = page.title()
        if "404" in title or "nicht gefunden" in title.lower():
            result["status"] = "not_found"
            result["error"] = f"404 page at {overview_url}"
            return result

        text = page.inner_text("body")
        result["source_url"] = overview_url

        # skiresort.de layout: prices in a tab-separated table:
        # Line N:   "Erwachsene\tJugendliche\tKinder"
        # Line N+1: "SFr. 74,-\tSFr. 59,-\tSFr. 37,-"   (CHF)
        # Line N+2: "ca. € 80,-\tca. € 63,-\tca. € 40,-" (EUR approx)

        lines = text.split("\n")
        header_idx = None
        for i, line in enumerate(lines):
            if "Erwachsene" in line and ("Jugend" in line or "Kinder" in line):
                header_idx = i
                break

        if header_idx is not None:
            headers = [h.strip() for h in lines[header_idx].split("\t")]
            col_map = {}
            for ci, h in enumerate(headers):
                if "Erwachsene" in h:
                    col_map["adult"] = ci
                elif "Jugend" in h:
                    col_map["youth"] = ci
                elif "Kinder" in h:
                    col_map["child"] = ci

            # Look at the next few lines for price rows
            eur_prices = {}
            chf_prices = {}
            for offset in range(1, 4):
                if header_idx + offset >= len(lines):
                    break
                row = lines[header_idx + offset].strip()
                if not row:
                    continue
                cells = [c.strip() for c in row.split("\t")]

                if "€" in row:
                    for key, ci in col_map.items():
                        if ci < len(cells):
                            eur_prices[key] = _parse_price(cells[ci])
                elif "SFr" in row or "CHF" in row:
                    for key, ci in col_map.items():
                        if ci < len(cells):
                            chf_prices[key] = _parse_price(cells[ci])

            # Prefer EUR; fall back to CHF with conversion
            if eur_prices.get("adult"):
                result["currency"] = "EUR"
                result["day_pass_adult_eur"] = eur_prices.get("adult")
                result["day_pass_youth16_eur"] = eur_prices.get("youth")
                result["day_pass_child13_eur"] = eur_prices.get("child")
            elif chf_prices.get("adult"):
                result["currency"] = "CHF"
                result["day_pass_adult_eur"] = round(chf_prices["adult"] * chf_to_eur, 2)
                if chf_prices.get("youth"):
                    result["day_pass_youth16_eur"] = round(chf_prices["youth"] * chf_to_eur, 2)
                if chf_prices.get("child"):
                    result["day_pass_child13_eur"] = round(chf_prices["child"] * chf_to_eur, 2)

        # Also look for family pass anywhere in the text
        family_match = re.search(r"Famili(?:en)?(?:karte|pass|ticket)?[^\n]*?(?:€|SFr\.)\s*(\d+(?:[.,]\d+)?)", text)
        if family_match:
            price = _parse_price(family_match.group(1))
            if price:
                result["family_pass_eur"] = round(price, 2)

        has_prices = result["day_pass_adult_eur"] is not None
        result["status"] = "scraped" if has_prices else "no_prices"
        if not has_prices:
            result["error"] = "Overview page loaded but no adult price found"

    except Exception as e:
        logger.warning("Error scraping %s: %s", slug, e)
        result["error"] = str(e)

    return result


def _scrape_country_batch(
    country: str,
    resorts: list[dict],
    cache_dir: Path,
    chf_to_eur: float,
    lock: Lock,
    progress: dict,
) -> list[tuple[str, dict, dict]]:
    """Scrape all resorts for one country in a dedicated browser. Returns [(rid, data, report_row), ...]."""
    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for resort in resorts:
            rid = resort["resort_id"]
            cache_file = cache_dir / f"{rid}.json"

            if cache_file.exists():
                data = json.loads(cache_file.read_text("utf-8"))
            else:
                slugs = _try_slugs(resort["name"])
                data = None
                for slug in slugs:
                    data = _scrape_resort(page, slug, chf_to_eur)
                    if data["status"] in ("scraped", "no_prices"):
                        break
                if data is None:
                    data = {"slug": slugs[0] if slugs else rid, "status": "not_found", "error": "No slug matched"}
                cache_file.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
                time.sleep(1)

            report_row = {
                "resort_id": rid,
                "name": resort["name"],
                "scraping_status": data.get("status", "error"),
                "source_url": data.get("source_url"),
                "attempted_url": data.get("slug", ""),
                "error_detail": data.get("error"),
            }
            results.append((rid, data, report_row))

            with lock:
                progress[country] = progress.get(country, 0) + 1

        browser.close()

    return results


def scrape_resorts(resorts: list[dict], cfg: dict) -> tuple[list[dict], pd.DataFrame]:
    """Scrape prices for all resorts (parallel per country, incremental via cache)."""
    chf_to_eur = cfg["costs"]["chf_to_eur"]
    raw = raw_dir(cfg, "resort_source")
    cache_dir = raw / "scraper"
    cache_dir.mkdir(parents=True, exist_ok=True)

    by_country: dict[str, list[dict]] = {}
    for r in resorts:
        by_country.setdefault(r.get("country", "??"), []).append(r)

    totals = {c: len(rs) for c, rs in by_country.items()}
    lock = Lock()
    progress: dict[str, int] = {c: 0 for c in by_country}

    def _print_progress():
        while not stop_flag:
            parts = []
            for c in sorted(totals):
                d = progress.get(c, 0)
                t = totals[c]
                pct = d / t * 100 if t else 100
                parts.append(f"{c}:{d}/{t}({pct:.0f}%)")
            total_done = sum(progress.values())
            total_all = sum(totals.values())
            pct_all = total_done / total_all * 100 if total_all else 100
            sys.stderr.write(f"\r  Scraping: {total_done}/{total_all} ({pct_all:.0f}%) [{' '.join(parts)}]   ")
            sys.stderr.flush()
            time.sleep(2)

    stop_flag = False
    progress_thread = Thread(target=_print_progress, daemon=True)
    progress_thread.start()

    all_results: dict[str, list[tuple[str, dict, dict]]] = {}
    threads: list[Thread] = []

    def _run_country(country, resorts_list):
        all_results[country] = _scrape_country_batch(
            country, resorts_list, cache_dir, chf_to_eur, lock, progress,
        )

    for country, resorts_list in by_country.items():
        t = Thread(target=_run_country, args=(country, resorts_list))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    stop_flag = True
    progress_thread.join(timeout=3)

    scrape_results = []
    report_rows = []
    for r in resorts:
        rid = r["resort_id"]
        c = r.get("country", "??")
        found = False
        for rid2, data, report_row in all_results.get(c, []):
            if rid2 == rid:
                scrape_results.append({"resort_id": rid, **data})
                report_rows.append(report_row)
                found = True
                break
        if not found:
            scrape_results.append({"resort_id": rid, "status": "error", "error": "not processed"})
            report_rows.append({"resort_id": rid, "name": r["name"], "scraping_status": "error"})

    total_all = sum(totals.values())
    sys.stderr.write(f"\r  Scraping: {total_all}/{total_all} (100%) done" + " " * 40 + "\n")
    sys.stderr.flush()

    report_df = pd.DataFrame(report_rows)
    logger.info(
        "Scraping done: %d scraped, %d no_prices, %d not_found, %d error",
        sum(1 for r in scrape_results if r.get("status") == "scraped"),
        sum(1 for r in scrape_results if r.get("status") == "no_prices"),
        sum(1 for r in scrape_results if r.get("status") == "not_found"),
        sum(1 for r in scrape_results if r.get("status") == "error"),
    )

    return scrape_results, report_df


def _size_class(slope_km: float | None) -> str:
    if slope_km is None:
        return "small"
    if slope_km < 30:
        return "small"
    if slope_km <= 100:
        return "medium"
    return "large"


def _fit_price_regression(
    resorts: list[dict],
    by_id: dict[str, dict],
    min_points: int = 5,
) -> dict[str, tuple]:
    """Fit log-linear regression: adult_price = a * log(slope_km) + b, per country.

    Also computes median ratios (youth/adult, child/adult, family/adult) per country.
    Returns {country: (a, b, ratios)} for countries with enough data.
    """
    import math

    country_data: dict[str, list[dict]] = {}
    for r in resorts:
        sr = by_id.get(r["resort_id"], {})
        slope = sr.get("slope_km") or r.get("slope_km")
        if (
            sr.get("status") == "scraped"
            and sr.get("day_pass_adult_eur") is not None
            and slope
            and slope > 0
        ):
            country_data.setdefault(r["country"], []).append({
                "log_slope": math.log(max(slope, 0.5)),
                "adult": sr["day_pass_adult_eur"],
                "youth": sr.get("day_pass_youth16_eur"),
                "child": sr.get("day_pass_child13_eur"),
                "family": sr.get("family_pass_eur"),
            })

    models: dict[str, tuple] = {}
    for country, pts in country_data.items():
        if len(pts) < min_points:
            continue
        xs = [p["log_slope"] for p in pts]
        ys = [p["adult"] for p in pts]
        n = len(xs)
        sx = sum(xs)
        sy = sum(ys)
        sxy = sum(x * y for x, y in zip(xs, ys))
        sxx = sum(x * x for x in xs)
        denom = n * sxx - sx * sx
        if abs(denom) < 1e-9:
            continue
        a = (n * sxy - sx * sy) / denom
        b = (sy - a * sx) / n

        ratios: dict[str, float] = {}
        for field, key in [("day_pass_youth16_eur", "youth"),
                           ("day_pass_child13_eur", "child"),
                           ("family_pass_eur", "family")]:
            pairs = [(p["adult"], p[key]) for p in pts
                     if p.get(key) is not None and p["adult"] > 0]
            if pairs:
                ratios[field] = statistics.median(v / a for a, v in pairs)
        models[country] = (a, b, ratios)
        logger.info(
            "Price regression %s: price = %.1f * log(slope) + %.1f  (n=%d, R²=%.2f)",
            country, a, b, n,
            1 - sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
            / max(sum((y - sy / n) ** 2 for y in ys), 1e-9),
        )
    return models


def impute_missing_prices(
    resorts: list[dict],
    scrape_results: list[dict],
    report_df: pd.DataFrame,
) -> tuple[list[dict], pd.DataFrame]:
    """Fill missing prices using log-linear regression on slope_km per country.

    Falls back to country+size_class peer median when regression unavailable.
    """
    import math

    by_id = {r["resort_id"]: r for r in scrape_results}

    for r in resorts:
        rid = r["resort_id"]
        sr = by_id.get(rid, {})
        slope = sr.get("slope_km") or r.get("slope_km")
        r["_size_class"] = _size_class(slope)

    # --- Regression models per country ---
    models = _fit_price_regression(resorts, by_id)

    # --- Fallback: country+size_class medians (original method) ---
    scraped_prices: dict[str, list[dict]] = {}
    for r in resorts:
        rid = r["resort_id"]
        sr = by_id.get(rid, {})
        if sr.get("status") == "scraped" and sr.get("day_pass_adult_eur") is not None:
            key = f"{r['country']}:{r['_size_class']}"
            scraped_prices.setdefault(key, []).append({
                "day_pass_adult_eur": sr["day_pass_adult_eur"],
                "day_pass_youth16_eur": sr.get("day_pass_youth16_eur"),
                "day_pass_child13_eur": sr.get("day_pass_child13_eur"),
                "family_pass_eur": sr.get("family_pass_eur"),
            })

    medians: dict[str, dict] = {}
    for key, prices in scraped_prices.items():
        m = {}
        for field in ["day_pass_adult_eur", "day_pass_youth16_eur", "day_pass_child13_eur", "family_pass_eur"]:
            vals = [p[field] for p in prices if p.get(field) is not None]
            m[field] = round(statistics.median(vals), 2) if vals else None
        medians[key] = m

    updated_report = report_df.copy()
    n_regression = 0
    n_median = 0
    for r in resorts:
        rid = r["resort_id"]
        sr = by_id.get(rid, {})
        if sr.get("status") == "scraped":
            continue

        slope = sr.get("slope_km") or r.get("slope_km")
        country = r["country"]
        model = models.get(country)

        if model and slope and slope > 0:
            a, b, ratios = model
            adult = max(round(a * math.log(max(slope, 0.5)) + b, 2), 5.0)
            sr["day_pass_adult_eur"] = adult
            for field, ratio in ratios.items():
                sr[field] = round(adult * ratio, 2)
            sr["status"] = "estimated"
            sr["source_url"] = None
            mask = updated_report["resort_id"] == rid
            updated_report.loc[mask, "scraping_status"] = "estimated"
            updated_report.loc[mask, "error_detail"] = (
                f"Regression ({country}, slope={slope:.1f}km)"
            )
            n_regression += 1
        else:
            key = f"{country}:{r['_size_class']}"
            peer_med = medians.get(key)
            if peer_med and peer_med.get("day_pass_adult_eur") is not None:
                sr["day_pass_adult_eur"] = peer_med["day_pass_adult_eur"]
                sr["day_pass_youth16_eur"] = peer_med.get("day_pass_youth16_eur")
                sr["day_pass_child13_eur"] = peer_med.get("day_pass_child13_eur")
                sr["family_pass_eur"] = peer_med.get("family_pass_eur")
                sr["status"] = "estimated"
                sr["source_url"] = None
                mask = updated_report["resort_id"] == rid
                updated_report.loc[mask, "scraping_status"] = "estimated"
                updated_report.loc[mask, "error_detail"] = (
                    f"Peer median ({key}, n={len(scraped_prices.get(key, []))})"
                )
                n_median += 1

    logger.info(
        "Imputation: %d via regression, %d via peer median, %d total",
        n_regression, n_median, n_regression + n_median,
    )

    for r in resorts:
        del r["_size_class"]

    return scrape_results, updated_report


def generate_provenance_chart(report_df: pd.DataFrame, figures_dir: Path) -> None:
    """Generate bar chart showing scraped vs estimated vs null prices per country."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        logger.warning("plotly not installed — skipping provenance chart")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)

    if "country" not in report_df.columns:
        logger.warning("No country column in report — skipping provenance chart")
        return

    countries = sorted(report_df["country"].dropna().unique())
    scraped_counts = []
    estimated_counts = []
    null_counts = []

    for c in countries:
        subset = report_df[report_df["country"] == c]
        scraped_counts.append(len(subset[subset["scraping_status"] == "scraped"]))
        estimated_counts.append(len(subset[subset["scraping_status"] == "estimated"]))
        null_counts.append(len(subset[subset["scraping_status"].isin(["not_found", "no_prices", "error"])]))

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Gescrapt (echte Preise)", x=countries, y=scraped_counts, marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Geschätzt (Peer-Median)", x=countries, y=estimated_counts, marker_color="#f39c12"))
    fig.add_trace(go.Bar(name="Keine Daten", x=countries, y=null_counts, marker_color="#e74c3c"))

    fig.update_layout(
        barmode="stack",
        title="Preisdaten-Herkunft je Land",
        xaxis_title="Land",
        yaxis_title="Anzahl Skigebiete",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    path = figures_dir / "fig_data_provenance.png"
    fig.write_image(str(path), width=1200, height=700)
    logger.info("Provenance chart saved: %s", path)
