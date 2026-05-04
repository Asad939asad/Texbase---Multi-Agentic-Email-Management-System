#!/usr/bin/python3
"""
Cotlook A-Index cotton price scraper.
Scrapes monthly data from ycharts.com and saves to JSON.
No browser window - simple HTTP requests only.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

URL = "https://ycharts.com/indicators/cotlook_aindex_cotton_price"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'cotlook_a_index.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_cotlook_a_index():
    print(f"Fetching Cotlook A-Index data from: {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    monthly_data = []

    # Both tables on the page share class="table"
    tables = soup.find_all("table", class_="table")
    for table in tables:
        rows = table.find("tbody")
        if not rows:
            continue
        for tr in rows.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) >= 2:
                date_text = cells[0].get_text(strip=True)
                value_text = cells[1].get_text(strip=True)
                try:
                    value = float(value_text)
                except ValueError:
                    value = value_text
                monthly_data.append({
                    "date": date_text,
                    "value": value
                })

    # Sort by date descending (most recent first)
    try:
        monthly_data.sort(
            key=lambda x: datetime.strptime(x["date"], "%B %d, %Y"),
            reverse=True
        )
    except Exception:
        pass  # Keep original order if parsing fails

    return monthly_data

def main():
    try:
        data = scrape_cotlook_a_index()

        print(f"\n--- Cotlook A-Index Data ({len(data)} months) ---")
        for entry in data[:5]:
            print(f"  {entry['date']}: {entry['value']}")
        if len(data) > 5:
            print(f"  ... and {len(data) - 5} more entries")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"\nData saved to: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
