"""
scraper.py
----------
Fetches company sustainability report links from the EFRAG Insights API.

Endpoint: POST https://api.insights.efrag.org/api/reports/data/
Returns all 648 companies in a single response — no pagination, no auth.

Output: data/efrag_pdf_links.json

Usage:
    python scraper.py                        # all companies
    python scraper.py --pdf-only             # skip HTML/xhtml reports
    python scraper.py --verified             # only correct_report=true
    python scraper.py --pdf-only --verified  # clean PDF subset (recommended)
    python scraper.py --dry-run              # print stats without saving
"""

import argparse
import json
import logging
from pathlib import Path

import requests

API_URL     = "https://api.insights.efrag.org/api/reports/data/"
OUTPUT_PATH = Path("data/bronze/efrag_pdf_links.json")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Content-Type":  "application/json",
    "Accept":        "application/json",
    "Origin":        "https://insights.efrag.org",
    "Referer":       "https://insights.efrag.org/",
    "User-Agent":    "Mozilla/5.0 ESG-research-bot/0.1 (academic research)",
}

PAYLOAD = {
    "year":          "2024",
    "region":        "Europe",
    "countries":     [],
    "fiNonFi":       ["Non-Financial", "Financial"],
    "industryGroup": [],
    "revenue":       [],
    "assets":        [],
    "question":      "Topical standard: Average # of Material topical standards",
}


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


def fetch(year: str = "2024") -> list[dict]:
    payload = {**PAYLOAD, "year": year}
    logger.info(f"POST {API_URL}")
    r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    if not r.ok:
        logger.error(f"HTTP {r.status_code}: {r.text[:500]}")
        r.raise_for_status()
    data = r.json()
    companies = data.get("companies", [])
    logger.info(f"Received {len(companies)} companies")
    return companies


def filter_records(
    companies: list[dict],
    pdf_only: bool,
    verified_only: bool,
) -> list[dict]:
    result = companies

    if verified_only:
        before = len(result)
        result = [c for c in result if c.get("correct_report") is True]
        logger.info(f"verified filter: {before} → {len(result)}")

    if pdf_only:
        before = len(result)
        result = [c for c in result if c.get("report_url_type") == "pdf"]
        logger.info(f"pdf-only filter: {before} → {len(result)}")

    return result


def summarise(records: list[dict]) -> None:
    countries = sorted({r.get("country", "unknown") for r in records})
    logger.info(f"{len(records)} records across {len(countries)} countries")
    logger.info(f"Countries: {countries}")


def main(year: str, pdf_only: bool, verified_only: bool, dry_run: bool) -> None:
    companies = fetch(year=year)
    records   = filter_records(companies, pdf_only=pdf_only, verified_only=verified_only)
    summarise(records)

    if dry_run:
        print(json.dumps(records[:5], indent=2, ensure_ascii=False))
        logger.info("Dry run — not saving")
        return

    OUTPUT_PATH.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Saved {len(records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch EFRAG report links")
    parser.add_argument("--year",       default="2024")
    parser.add_argument("--pdf-only",   action="store_true", help="Skip HTML reports")
    parser.add_argument("--verified",   action="store_true", help="Only correct_report=true")
    parser.add_argument("--dry-run",    action="store_true", help="Print sample, don't save")
    args = parser.parse_args()

    main(
        year          = args.year,
        pdf_only      = args.pdf_only,
        verified_only = args.verified,
        dry_run       = args.dry_run,
    )