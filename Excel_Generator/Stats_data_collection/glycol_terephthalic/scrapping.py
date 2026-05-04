#!/usr/bin/python3
"""
Terephthalic Acid (TPA) and Ethylene Glycol price scraper.
Scrapes regional pricing from businessanalytiq.com and saves to JSON.
Simple HTTP request - no browser window needed.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

URLS = {
    "terephthalic_acid": "https://businessanalytiq.com/procurementanalytics/index/terephthalic-acid-price-index/",
    "ethylene_glycol": "https://businessanalytiq.com/procurementanalytics/index/ethylene-glycol-price-index/"
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'glycol_terephthalic.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_price_entry(text):
    """Parse 'North America:US$0.96/KG, -3% down' into structured data."""
    entry = {"region": None, "price": None, "change": None}
    
    # Split region from value
    parts = text.split(":", 1)
    if len(parts) == 2:
        entry["region"] = parts[0].strip()
        value_part = parts[1].strip()
        
        # Extract price: US$0.96/KG
        price_match = re.search(r'US\$?([\d.]+)/KG', value_part)
        if price_match:
            entry["price"] = f"US${price_match.group(1)}/KG"
        
        # Extract change: -3% down, 2.9% up, unchanged
        change_match = re.search(r'([-+]?[\d.]+%\s*\w+|unchanged)', value_part)
        if change_match:
            entry["change"] = change_match.group(1).strip()
    
    return entry

def scrape_single(url, label):
    print(f"  Fetching: {label} ...")
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    result = {"title": None, "regions": []}

    # Find the h3 with price info
    for h3 in soup.find_all("h3"):
        h3_text = h3.get_text(strip=True)
        if "price" in h3_text.lower() and "2026" in h3_text:
            result["title"] = h3_text

            # The ul with regional prices is the next sibling
            ul = h3.find_next("ul")
            if ul:
                for li in ul.find_all("li"):
                    entry = parse_price_entry(li.get_text(strip=True))
                    if entry["region"]:
                        result["regions"].append(entry)
            break

    return result

def main():
    print("Scraping TPA & Ethylene Glycol prices")
    
    all_data = {"scraped_at": datetime.now().isoformat()}

    for key, url in URLS.items():
        try:
            data = scrape_single(url, key)
            all_data[key] = data
            print(f"  Found {len(data['regions'])} regions for {key}")
        except Exception as e:
            print(f"  Error scraping {key}: {e}")
            all_data[key] = {"error": str(e)}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)

    print(f"\nData saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
