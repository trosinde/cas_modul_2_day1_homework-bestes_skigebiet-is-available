"""Playwright-based menu/Speisekarte finder for restaurant websites."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

from common.log import get_logger

logger = get_logger("menu_scraper")

MENU_LINK_PATTERNS = [
    re.compile(r"speisekarte", re.IGNORECASE),
    re.compile(r"menükarte", re.IGNORECASE),
    re.compile(r"menuekarte", re.IGNORECASE),
    re.compile(r"speisen", re.IGNORECASE),
    re.compile(r"küche", re.IGNORECASE),
    re.compile(r"kueche", re.IGNORECASE),
    re.compile(r"kulinar", re.IGNORECASE),
    re.compile(r"essen\s*(?:&|und|e)\s*trinken", re.IGNORECASE),
    re.compile(r"gastronomie", re.IGNORECASE),
    re.compile(r"piatti", re.IGNORECASE),
    re.compile(r"cucina", re.IGNORECASE),
    re.compile(r"menu(?!.*navigat)", re.IGNORECASE),
    re.compile(r"carte", re.IGNORECASE),
    re.compile(r"karte(?!.*land)", re.IGNORECASE),
    re.compile(r"restaurant(?!.*hotel)", re.IGNORECASE),
]

PRICE_RE = re.compile(r"\d+[.,]\d{2}\s*(?:€|EUR|CHF|Fr\.?|SFr\.?)")

COMMON_MENU_SUFFIXES = [
    "/speisekarte",
    "/menu",
    "/restaurant",
    "/gastronomie",
    "/kueche",
    "/essen-trinken",
]

_MAX_CACHED_TEXT = 50_000


@dataclass
class MenuResult:
    """Result of a menu page search."""

    found: bool
    menu_url: str | None = None
    menu_html: str | None = None
    menu_text: str | None = None
    is_pdf: bool = False
    error: str | None = None


def find_menu_page(website_url: str, cache_dir: Path | None = None) -> MenuResult:
    """Navigate to a restaurant website, locate the Speisekarte, and return its content."""
    cached = _read_cache(cache_dir, website_url)
    if cached is not None:
        return cached

    try:
        result = _scrape_menu(website_url)
    except Exception as exc:
        logger.warning("Playwright error for %s: %s", website_url, exc)
        result = MenuResult(found=False, error=f"Playwright error: {exc}")

    _write_cache(result, cache_dir, website_url)
    return result


def _scrape_menu(website_url: str) -> MenuResult:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            return _scrape_in_browser(browser, website_url)
        finally:
            browser.close()


def _scrape_in_browser(browser, website_url: str) -> MenuResult:
    context = browser.new_context(
        user_agent="Mozilla/5.0 (compatible; SkiResortBot/1.0; academic research)",
        locale="de-CH",
    )
    page = context.new_page()
    page.set_default_timeout(15_000)

    try:
        page.goto(website_url, wait_until="domcontentloaded", timeout=15_000)
    except Exception as exc:
        return MenuResult(found=False, error=f"Navigation failed: {exc}")

    menu_link = _find_menu_link(page)

    if menu_link:
        result = _follow_menu_link(page, menu_link)
        if result is not None:
            return result

    result = _try_common_suffixes(page, website_url)
    if result is not None:
        return result

    return _try_main_page_prices(page, website_url)


def _follow_menu_link(page, menu_link: str) -> MenuResult | None:
    if _looks_like_pdf(menu_link):
        return _handle_pdf_menu(menu_link)

    try:
        page.goto(menu_link, wait_until="domcontentloaded", timeout=15_000)
        html = page.content()
        text = page.inner_text("body")
        return MenuResult(found=True, menu_url=menu_link, menu_html=html, menu_text=text)
    except Exception as exc:
        logger.debug("Failed to follow menu link %s: %s", menu_link, exc)
        return None


def _try_common_suffixes(page, website_url: str) -> MenuResult | None:
    base = website_url.rstrip("/")
    for suffix in COMMON_MENU_SUFFIXES:
        try:
            resp = page.goto(base + suffix, wait_until="domcontentloaded", timeout=8_000)
        except Exception:
            continue
        if resp and resp.ok:
            text = page.inner_text("body")
            if PRICE_RE.search(text):
                return MenuResult(
                    found=True,
                    menu_url=base + suffix,
                    menu_html=page.content(),
                    menu_text=text,
                )
    return None


def _try_main_page_prices(page, website_url: str) -> MenuResult:
    try:
        page.goto(website_url, wait_until="domcontentloaded", timeout=10_000)
        html = page.content()
        text = page.inner_text("body")
    except Exception as exc:
        return MenuResult(found=False, error=f"Final fallback failed: {exc}")

    if PRICE_RE.search(text):
        return MenuResult(found=True, menu_url=website_url, menu_html=html, menu_text=text)
    return MenuResult(found=False, error="No menu page found")


def _find_menu_link(page) -> str | None:
    links = page.query_selector_all("a[href]")
    candidates: list[tuple[str, str]] = []

    for link in links:
        try:
            text = (link.inner_text() or "").strip()
            title = link.get_attribute("title") or ""
            href = link.get_attribute("href") or ""
            combined = f"{text} {href} {title}"
        except Exception:
            continue

        for pattern in MENU_LINK_PATTERNS:
            if pattern.search(combined):
                try:
                    full_url = page.evaluate("(el) => el.href", link)
                except Exception:
                    break
                if full_url:
                    candidates.append((full_url, text))
                break

    if not candidates:
        return None

    for url, text in candidates:
        if re.search(r"speisekarte|menü|menu|speisen", text, re.IGNORECASE):
            return url

    return candidates[0][0]


def _looks_like_pdf(url: str) -> bool:
    return url.lower().rstrip("?&#").endswith(".pdf")


def _handle_pdf_menu(pdf_url: str) -> MenuResult:
    import httpx
    import pdfplumber

    try:
        resp = httpx.get(pdf_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        return MenuResult(found=False, menu_url=pdf_url, error=f"PDF download failed: {exc}")

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            tmp = Path(f.name)

        parts: list[str] = []
        with pdfplumber.open(tmp) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text()
                if t:
                    parts.append(t)

        text = "\n\n".join(parts)
        if text.strip():
            return MenuResult(found=True, menu_url=pdf_url, menu_text=text, is_pdf=True)
        return MenuResult(
            found=False,
            menu_url=pdf_url,
            error="PDF has no extractable text (likely image-based)",
        )
    except Exception as exc:
        return MenuResult(found=False, menu_url=pdf_url, error=f"PDF extraction failed: {exc}")
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def _cache_key(website_url: str) -> str:
    return hashlib.md5(website_url.encode()).hexdigest()[:12]


def _read_cache(cache_dir: Path | None, website_url: str) -> MenuResult | None:
    if not cache_dir:
        return None
    path = cache_dir / f"{_cache_key(website_url)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        return MenuResult(**data)
    except Exception:
        return None


def _write_cache(result: MenuResult, cache_dir: Path | None, website_url: str) -> None:
    if not cache_dir:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(result)
        data.pop("menu_html", None)
        if data.get("menu_text") and len(data["menu_text"]) > _MAX_CACHED_TEXT:
            data["menu_text"] = data["menu_text"][:_MAX_CACHED_TEXT]
        path = cache_dir / f"{_cache_key(website_url)}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception as exc:
        logger.debug("Cache write failed for %s: %s", website_url, exc)
