"""
scraper.py
----------
Scrapes company sustainability report PDF links from the EFRAG Knowledge Hub
report repository: https://knowledgehub.efrag.org/eng/report-repository

The portal is a JavaScript SPA — requests + BeautifulSoup won't work here.
We use Playwright to drive a real browser, wait for the table to render,
paginate through all results, and extract company name, country, sector,
and PDF download URL.

Output: data/efrag_pdf_links.json
    List of dicts matching the schema expected by download_reports.py:
    [{"name": "...", "country": "...", "sector": "...", "report_url": "..."}, ...]

Usage:
    pip install playwright
    playwright install chromium
    python scraper.py
    python scraper.py --max 50          # limit to first 50 companies
    python scraper.py --sector Energy   # filter by sector label
    python scraper.py --headless false  # watch the browser (useful for debugging)
"""

import argparse
import json
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://knowledgehub.efrag.org/eng/report-repository"
OUTPUT_PATH = Path("data/efrag_pdf_links.json")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# How long to wait for the table to appear after navigation / pagination (ms)
TABLE_TIMEOUT = 15_000
# Polite delay between page turns (seconds) — don't hammer their server
PAGE_DELAY = 1.5


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("scraper")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


logger = setup_logger()


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

def scrape(max_records: int | None = None, sector_filter: str | None = None, headless: bool = True) -> list[dict]:
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 ESG-research-bot/0.1 (academic research)"
        )
        page = context.new_page()

        logger.info(f"Navigating to {BASE_URL}")
        page.goto(BASE_URL, wait_until="networkidle")

        # Wait for the report table to appear
        try:
            page.wait_for_selector("table, [class*='report'], [class*='table']", timeout=TABLE_TIMEOUT)
        except PlaywrightTimeout:
            logger.error("Timed out waiting for report table — the page structure may have changed.")
            logger.info("Saving a screenshot to debug_screenshot.png for inspection.")
            page.screenshot(path="debug_screenshot.png")
            browser.close()
            return records

        # Apply sector filter if requested (look for a dropdown or filter input)
        if sector_filter:
            logger.info(f"Applying sector filter: {sector_filter}")
            _apply_filter(page, sector_filter)

        page_num = 1

        while True:
            logger.info(f"Scraping page {page_num}...")

            # Parse current page
            rows = _extract_rows(page)

            if not rows:
                logger.warning(f"No rows found on page {page_num} — stopping.")
                break

            records.extend(rows)
            logger.info(f"Page {page_num}: found {len(rows)} records (total: {len(records)})")

            if max_records and len(records) >= max_records:
                records = records[:max_records]
                logger.info(f"Reached max_records={max_records}, stopping.")
                break

            # Try to go to next page
            next_btn = _find_next_button(page)
            if next_btn is None:
                logger.info("No next page button found — done.")
                break

            try:
                next_btn.click()
                time.sleep(PAGE_DELAY)
                page.wait_for_load_state("networkidle")
                page_num += 1
            except Exception as e:
                logger.warning(f"Failed to navigate to next page: {e}")
                break

        browser.close()

    return records


def _apply_filter(page, sector_filter: str) -> None:
    """
    Attempt to apply a sector filter via a dropdown or search box.
    This is best-effort — if the filter UI changes, update the selectors here.
    """
    try:
        # Try a select dropdown first
        select = page.query_selector("select[name*='sector'], select[name*='industry']")
        if select:
            select.select_option(label=sector_filter)
            time.sleep(PAGE_DELAY)
            return

        # Try a text search / filter input
        filter_input = page.query_selector("input[placeholder*='filter'], input[placeholder*='search']")
        if filter_input:
            filter_input.fill(sector_filter)
            filter_input.press("Enter")
            time.sleep(PAGE_DELAY)
            return

        logger.warning(f"Could not find a sector filter UI element — scraping all sectors.")
    except Exception as e:
        logger.warning(f"Filter application failed: {e} — scraping all sectors.")


def _extract_rows(page) -> list[dict]:
    """
    Extract company records from the current page state.
    Tries multiple selector strategies since the portal may use different markup.
    """
    rows = []

    # Strategy 1: Standard HTML table rows
    table_rows = page.query_selector_all("table tbody tr")
    if table_rows:
        for row in table_rows:
            cells = row.query_selector_all("td")
            if len(cells) < 2:
                continue

            record = _parse_table_row(cells, row)
            if record:
                rows.append(record)
        return rows

    # Strategy 2: Card / list layout (common in modern SPAs)
    cards = page.query_selector_all("[class*='report-card'], [class*='company-card'], [class*='result-item']")
    if cards:
        for card in cards:
            record = _parse_card(card)
            if record:
                rows.append(record)
        return rows

    # Strategy 3: Dump all links ending in .pdf as a fallback
    logger.warning("Could not find table or card layout — falling back to PDF link extraction.")
    pdf_links = page.query_selector_all("a[href$='.pdf'], a[href*='/download']")
    for link in pdf_links:
        href = link.get_attribute("href")
        text = link.inner_text().strip()
        if href:
            rows.append({
                "name": text or "unknown",
                "country": "unknown",
                "sector": "unknown",
                "report_url": _resolve_url(href),
            })

    return rows


def _parse_table_row(cells, row) -> dict | None:
    """Parse a table row into a record dict. Column order may vary — adjust as needed."""
    try:
        texts = [c.inner_text().strip() for c in cells]

        # Try to find a PDF link anywhere in the row
        link = row.query_selector("a[href$='.pdf'], a[href*='download'], a[href*='report']")
        report_url = _resolve_url(link.get_attribute("href")) if link else None

        if not report_url:
            return None

        # Best-effort column mapping — inspect the portal and adjust these indices
        # Common layout: [company_name, country, sector, year, link]
        return {
            "name": texts[0] if len(texts) > 0 else "unknown",
            "country": texts[1] if len(texts) > 1 else "unknown",
            "sector": texts[2] if len(texts) > 2 else "unknown",
            "report_url": report_url,
        }
    except Exception as e:
        logger.debug(f"Row parse failed: {e}")
        return None


def _parse_card(card) -> dict | None:
    """Parse a card element into a record dict."""
    try:
        name_el = card.query_selector("[class*='name'], [class*='title'], h2, h3")
        country_el = card.query_selector("[class*='country']")
        sector_el = card.query_selector("[class*='sector'], [class*='industry']")
        link_el = card.query_selector("a[href$='.pdf'], a[href*='download']")

        if not link_el:
            return None

        return {
            "name": name_el.inner_text().strip() if name_el else "unknown",
            "country": country_el.inner_text().strip() if country_el else "unknown",
            "sector": sector_el.inner_text().strip() if sector_el else "unknown",
            "report_url": _resolve_url(link_el.get_attribute("href")),
        }
    except Exception as e:
        logger.debug(f"Card parse failed: {e}")
        return None


def _find_next_button(page):
    """Find the pagination next button. Returns the element or None."""
    selectors = [
        "button[aria-label*='next' i]",
        "a[aria-label*='next' i]",
        "[class*='pagination'] [class*='next']",
        "button:has-text('Next')",
        "a:has-text('Next')",
        "li.next > a",
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible() and btn.is_enabled():
                return btn
        except Exception:
            continue
    return None


def _resolve_url(href: str | None) -> str | None:
    """Make relative URLs absolute."""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://knowledgehub.efrag.org{href}"
    return f"https://knowledgehub.efrag.org/{href}"


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape EFRAG report repository for PDF links")
    parser.add_argument("--max", type=int, default=None, help="Max number of records to collect")
    parser.add_argument("--sector", type=str, default=None, help="Filter by sector label (e.g. 'Energy')")
    parser.add_argument("--headless", type=str, default="true", choices=["true", "false"],
                        help="Run browser headlessly (default: true). Use 'false' to watch.")
    args = parser.parse_args()

    headless = args.headless.lower() == "true"

    logger.info("Starting EFRAG scraper")
    records = scrape(max_records=args.max, sector_filter=args.sector, headless=headless)

    if not records:
        logger.error("No records collected. Run with --headless false to debug visually.")
    else:
        OUTPUT_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved {len(records)} records to {OUTPUT_PATH}")

        # Quick summary
        countries = {r["country"] for r in records}
        sectors = {r["sector"] for r in records}
        logger.info(f"Countries: {sorted(countries)}")
        logger.info(f"Sectors: {sorted(sectors)}")
        