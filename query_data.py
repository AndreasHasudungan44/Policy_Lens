import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import requests


INPUT_JSON = "/Users/andreasp/personal-projects/RAG_App for Policy Eval/data/efrag_pdf_links.json"
OUT_DIR = Path("data/raw_efrag")
OUT_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 ESG-research-bot/0.1"
})


def safe_name(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()

    if path.endswith(".pdf"):
        return ".pdf"
    if content_type and "pdf" in content_type.lower():
        return ".pdf"
    if path.endswith(".xhtml"):
        return ".xhtml"
    if path.endswith(".html") or path.endswith(".htm"):
        return ".html"
    return ".bin"


def derive_name_country(rec: dict, final_url: str | None = None) -> tuple[str, str]:
    name = str(rec.get("name") or rec.get("company_name") or "").strip()
    country = str(rec.get("country") or "unknown").strip() or "unknown"

    if name:
        return name, country

    candidate_url = final_url or str(rec.get("report_url") or rec.get("url") or "")
    parsed = urlparse(candidate_url)

    query_params = parse_qs(parsed.query)
    if "q" in query_params and query_params["q"]:
        candidate_url = unquote(query_params["q"][0])
        parsed = urlparse(candidate_url)

    slug = Path(unquote(parsed.path)).stem
    slug = slug or "unknown"
    slug = slug.replace("-", " ").replace("_", " ").strip()

    return slug, country


with open(INPUT_JSON, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

if isinstance(raw_data, dict):
    if "companies" in raw_data and isinstance(raw_data["companies"], list):
        records = raw_data["companies"]
    else:
        raise ValueError("Expected a top-level 'companies' list in the input JSON.")
elif isinstance(raw_data, list):
    if all(isinstance(item, dict) for item in raw_data):
        records = raw_data
    elif all(isinstance(item, str) for item in raw_data):
        records = [{"report_url": item} for item in raw_data]
    else:
        raise ValueError("Expected the input JSON to be a list of dicts or a list of URLs.")
else:
    raise ValueError("Unsupported JSON structure in INPUT_JSON.")

download_log = []

for rec in records:
    if not isinstance(rec, dict):
        download_log.append({
            "name": "unknown",
            "country": "unknown",
            "report_url": str(rec),
            "status": "error",
            "error": f"Unsupported record type: {type(rec).__name__}",
        })
        print(f"FAIL unsupported record type: {type(rec).__name__}")
        continue

    url = rec.get("report_url") or rec.get("url")
    name, country = derive_name_country(rec)

    if not url:
        download_log.append({
            "name": name,
            "country": country,
            "report_url": None,
            "status": "error",
            "error": "Missing report_url",
        })
        print(f"FAIL {name} -> missing report_url")
        continue

    try:
        r = session.get(url, timeout=60, allow_redirects=True)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        ext = guess_extension(str(r.url), content_type)

        final_name, final_country = derive_name_country(rec, str(r.url))
        filename = f"{safe_name(final_name)}__{safe_name(final_country)}{ext}"
        filepath = OUT_DIR / filename
        filepath.write_bytes(r.content)

        download_log.append({
            "name": final_name,
            "country": final_country,
            "report_url": url,
            "final_url": str(r.url),
            "content_type": content_type,
            "status": "ok",
            "saved_as": str(filepath),
        })
        print(f"OK   {final_name} -> {filename}")

    except Exception as e:
        download_log.append({
            "name": name,
            "country": country,
            "report_url": url,
            "status": "error",
            "error": str(e),
        })
        print(f"FAIL {name} -> {e}")

with open("data/efrag_download_log.json", "w", encoding="utf-8") as f:
    json.dump(download_log, f, indent=2, ensure_ascii=False)