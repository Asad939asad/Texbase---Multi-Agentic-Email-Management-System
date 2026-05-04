#!/usr/bin/python3
"""
Pakistan cotton rate scraper.
Scrapes from kissanstore.pk and extracts pricing numbers into JSON.
No browser window - simple HTTP requests only.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

URL = "https://kissanstore.pk/cotton-rate-in-pakistan/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'cotton_pakistan.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def extract_prices(text):
    """Extract all price-related numbers from the paragraph text."""
    data = {}

    # Range: "Rs. 7,350/- PKR to Rs. 9,800/-"
    range_match = re.search(r'Rs\.?\s*([\d,]+)\s*/?\-?\s*PKR?\s*to\s*Rs\.?\s*([\d,]+)', text, re.IGNORECASE)
    if range_match:
        data["price_min_per_40kg_pkr"] = int(range_match.group(1).replace(",", ""))
        data["price_max_per_40kg_pkr"] = int(range_match.group(2).replace(",", ""))

    # Per 40 Kg mention
    per40_match = re.search(r'Per\s+40\s*Kg', text, re.IGNORECASE)
    if per40_match:
        data["unit"] = "Per 40 Kg"

    # Per Kg price: "245 Rs Per Kg"
    perkg_match = re.search(r'([\d,]+)\s*Rs\s*Per\s*Kg', text, re.IGNORECASE)
    if perkg_match:
        data["price_per_kg_pkr"] = int(perkg_match.group(1).replace(",", ""))

    return data

def scrape_cotton_pakistan():
    print(f"Fetching Pakistan cotton rates from: {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the paragraph containing "Cotton Rate in Pakistan"
    target_paragraph = None
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if "Cotton Rate in Pakistan" in text and "Rs." in text:
            target_paragraph = text
            break

    if not target_paragraph:
        print("Could not find the target paragraph.")
        return None

    prices = extract_prices(target_paragraph)

    output = {
        "scraped_at": datetime.now().isoformat(),
        "source": URL,
        "paragraph": target_paragraph,
        "extracted_prices": prices
    }

    return output

def main():
    try:
        data = scrape_cotton_pakistan()

        if data:
            print("\n--- Pakistan Cotton Rate ---")
            print(f"Paragraph: {data['paragraph'][:120]}...")
            print(f"\nExtracted Prices:")
            for k, v in data["extracted_prices"].items():
                print(f"  {k}: {v}")

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            print(f"\nData saved to: {OUTPUT_FILE}")
        else:
            print("No data extracted.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
