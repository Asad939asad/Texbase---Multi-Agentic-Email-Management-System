#!/usr/bin/python3
"""
Brent Oil price scraper from Business Insider.
Simple HTTP request - no browser window needed.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

URL = "https://markets.businessinsider.com/commodities/oil-price"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'brent_oil.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_brent_oil():
    print(f"Fetching Brent Oil price from: {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": URL,
        "label": "Oil (Brent)",
        "category": "Price",
        "current_value": None,
        "previous_close": None,
        "absolute_change": None,
        "relative_change": None,
        "time": None
    }

    # Try embedded JSON in script tag first (most reliable)
    for script in soup.find_all("script"):
        script_text = script.string or ""
        if "priceSection" in script_text and "currentValue" in script_text:
            try:
                match = re.search(r'priceSection:\s*(\{.+?\})\s*\n', script_text, re.DOTALL)
                if match:
                    raw = match.group(1)
                    price_json = json.loads(raw.split(',"valuePushApi"')[0] + "}")
                    data["current_value"] = price_json.get("currentValue")
                    data["previous_close"] = price_json.get("previousClose")
                    data["absolute_change"] = price_json.get("absoluteValue")
                    data["relative_change"] = str(price_json.get("relativeValue", "")) + "%"
                    data["time"] = price_json.get("time")
                    data["label"] = price_json.get("label", data["label"])
                    break
            except Exception:
                pass

    # Fallback to HTML elements
    if data["current_value"] is None:
        el = soup.find("span", class_="price-section__current-value")
        if el:
            data["current_value"] = el.get_text(strip=True)
        el = soup.find("span", class_="price-section__absolute-value")
        if el:
            data["absolute_change"] = el.get_text(strip=True)
        el = soup.find("span", class_="price-section__relative-value")
        if el:
            data["relative_change"] = el.get_text(strip=True)

    return data

def main():
    try:
        data = scrape_brent_oil()

        print("\n--- Brent Oil Price ---")
        print(f"Current:  {data['current_value']}")
        print(f"Previous: {data['previous_close']}")
        print(f"Change:   {data['absolute_change']} ({data['relative_change']})")
        print(f"Time:     {data['time']}")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"\nData saved to: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
