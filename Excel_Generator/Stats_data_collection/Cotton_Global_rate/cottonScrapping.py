#!/usr/bin/python3
"""
Simple cotton price scraper - no browser window, just HTTP requests.
Scrapes from Business Insider and saves to JSON in the same folder.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

URL = "https://markets.businessinsider.com/commodities/cotton-price"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'cotton_prices.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_cotton_price():
    print(f"Fetching cotton price from: {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # --- 1. Extract main price data ---
    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": URL,
        "label": "Cotton",
        "category": "Price",
        "current_value": None,
        "absolute_change": None,
        "relative_change": None,
        "time": None,
        "unit_conversions": []
    }
    
    # Current price
    current_val = soup.find("span", class_="price-section__current-value")
    if current_val:
        data["current_value"] = current_val.get_text(strip=True)
        
    # Absolute change (+0.01)
    abs_val = soup.find("span", class_="price-section__absolute-value")
    if abs_val:
        data["absolute_change"] = abs_val.get_text(strip=True)
    
    # Relative change (+1.56%)
    rel_val = soup.find("span", class_="price-section__relative-value")
    if rel_val:
        data["relative_change"] = rel_val.get_text(strip=True)
    
    # Timestamp
    time_span = soup.find("span", class_="push-data")
    if time_span:
        data["time"] = time_span.get_text(strip=True)
    
    # Also try to extract from the embedded JSON in the script tag
    for script in soup.find_all("script"):
        script_text = script.string or ""
        if "priceSection" in script_text and "currentValue" in script_text:
            try:
                import re
                match = re.search(r'priceSection:\s*(\{.+?\})\s*\n', script_text, re.DOTALL)
                if match:
                    raw = match.group(1)
                    # Clean up nested objects that break simple parsing
                    price_json = json.loads(raw.split(',"valuePushApi"')[0] + "}")
                    data["current_value"] = str(price_json.get("currentValue", data["current_value"]))
                    data["previous_close"] = str(price_json.get("previousClose", ""))
                    data["absolute_change"] = str(price_json.get("absoluteValue", data["absolute_change"]))
                    data["relative_change"] = str(price_json.get("relativeValue", data["relative_change"])) + "%"
            except Exception:
                pass  # Fall back to HTML-parsed values
    
    # --- 2. Calculate unit conversions from the price per pound ---
    # The HTML table is JS-rendered and not in raw HTTP response,
    # so we compute it directly from the extracted price.
    try:
        price_per_lb = float(data["current_value"])
        price_per_kg = round(price_per_lb / 0.453592, 2)
        price_per_oz = round(price_per_lb / 16, 2)
        data["unit_conversions"] = [
            {
                "conversion": "1 Pound ≈ 0.453 Kilograms",
                "cotton_price_label": "Cotton Price Per 1 Kilogram",
                "price": f"{price_per_kg} USD"
            },
            {
                "conversion": "1 Pound = 16 Ounces",
                "cotton_price_label": "Cotton Price Per 1 Ounce",
                "price": f"{price_per_oz} USD"
            }
        ]
    except (ValueError, TypeError):
        pass  # Keep unit_conversions empty if price can't be parsed
    
    return data

def main():
    try:
        data = scrape_cotton_price()
        
        print("\n--- Cotton Price Data ---")
        print(f"Current Value: {data['current_value']}")
        print(f"Change:        {data['absolute_change']} ({data['relative_change']})")
        print(f"Time:          {data['time']}")
        
        if data["unit_conversions"]:
            print("\nUnit Conversions:")
            for uc in data["unit_conversions"]:
                print(f"  {uc['conversion']} -> {uc['price']}")
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f"\nData saved to: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
