"""
Leadership Change Finder — South Coast MA Manufacturing
---------------------------------------------------------
Scans SEC EDGAR's free full-text search for recent 8-K filings that report
Item 5.02 (Departure/Appointment of Directors or Officers) from companies
headquartered in Massachusetts.

IMPORTANT LIMITATION: This only catches PUBLIC companies (they're legally
required to file 8-Ks). Most South Coast manufacturers in your 50-1,000
employee range are private and won't show up here — for those, LinkedIn,
ZoomInfo, or local business journals (SouthCoast Business Bulletin,
Providence Business News) are your real source. This script covers the
free, official, zero-cost slice of the signal: public companies only.

Usage:
    pip install requests
    python leadership_changes.py
"""

import requests
import time
import json
from datetime import datetime, timedelta

# ---- CONFIG ----------------------------------------------------------
DAYS_BACK = 60
LOCATION_CODE = "MA"          # principal executive offices in Massachusetts
FORM_TYPE = "8-K"
ITEM_CODE = "5.02"            # Departure/Appointment of Directors/Officers
# Manufacturing-related SIC codes start with 2 or 3 (e.g. 2000-3999).
# EDGAR full-text search doesn't let us filter by SIC range directly,
# so we filter manually after fetching results (see is_manufacturing_sic).
OUTPUT_FILE = "leadership_changes_results.json"
# -----------------------------------------------------------------------

HEADERS = {
    # SEC requires a real User-Agent identifying you/your use case
    "User-Agent": "Jarrett - Element2Group BD Research jarrett@example.com"
}

BASE_URL = "https://efts.sec.gov/LATEST/search-index"


def is_manufacturing_sic(sic: str) -> bool:
    """Rough filter: SIC codes 2000-3999 are manufacturing."""
    if not sic or not sic.isdigit():
        return False
    return 2000 <= int(sic) <= 3999


def fetch_filings():
    end = datetime.today()
    start = end - timedelta(days=DAYS_BACK)

    params = {
        "q": '"Item 5.02"',
        "forms": FORM_TYPE,
        "dateRange": "custom",
        "startdt": start.strftime("%Y-%m-%d"),
        "enddt": end.strftime("%Y-%m-%d"),
        "locationCode": LOCATION_CODE,
    }

    all_hits = []
    frm = 0
    while True:
        params["from"] = frm
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        all_hits.extend(hits)
        frm += len(hits)

        total = data.get("hits", {}).get("total", {}).get("value", 0)
        if frm >= total:
            break

        time.sleep(0.2)  # stay well under SEC's rate limit

    return all_hits


def build_filing_url(hit):
    adsh, fname = hit["_id"].split(":", 1)
    cik = int(hit["_source"]["ciks"][0])
    folder = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{fname}"


def main():
    print(f"Searching EDGAR for {FORM_TYPE} filings (Item {ITEM_CODE}) "
          f"in {LOCATION_CODE}, last {DAYS_BACK} days...\n")

    hits = fetch_filings()
    results = []

    for hit in hits:
        src = hit["_source"]
        if "5.02" not in src.get("items", []):
            continue  # only keep filings that actually flagged 5.02

        sic = src.get("sic", "")
        company = ", ".join(src.get("display_names", []))
        filed = src.get("file_date", "")
        url = build_filing_url(hit)

        result = {
            "company": company,
            "sic_code": sic,
            "filed_date": filed,
            "filing_url": url,
            "likely_manufacturing": is_manufacturing_sic(sic),
        }
        results.append(result)

    # Sort: manufacturing hits first, then by most recent
    results.sort(key=lambda r: (not r["likely_manufacturing"], r["filed_date"]), reverse=False)

    print(f"Found {len(results)} executive-change 8-K filings in MA "
          f"over the last {DAYS_BACK} days:\n")

    for r in results:
        tag = "[MANUFACTURING]" if r["likely_manufacturing"] else "[other industry]"
        print(f"{tag} {r['company']}  —  filed {r['filed_date']}")
        print(f"   {r['filing_url']}\n")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved full results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
