#!/usr/bin/python3
"""
ZCE Cotton No.1 futures price scraper.
Extracts pricing data from barchart.com embedded JSON and saves to JSON.
No browser window - simple HTTP requests only.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

URL = "https://www.barchart.com/futures/quotes/WQ*0/futures-prices"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'zce_cotton.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

def scrape_zce_cotton():
    print(f"Fetching ZCE Cotton data from: {URL}")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # The price data is embedded in the data-ng-init attribute of the page-title div
    header_div = soup.find("div", class_="page-title")
    
    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": URL,
        "symbol": None,
        "symbol_name": None,
        "contract_name": None,
        "exchange": None,
        "last_price": None,
        "price_change": None,
        "percent_change": None,
        "trade_date": None,
        "daily_last_price": None,
        "point_value": None,
        "category": None
    }

    if header_div and header_div.get("data-ng-init"):
        init_text = header_div["data-ng-init"]
        
        # Extract the JSON object from init({...})
        match = re.search(r'init\((\{.+\})\)', init_text, re.DOTALL)
        if match:
            try:
                init_json = json.loads(match.group(1))
                data["symbol"] = init_json.get("symbol")
                data["symbol_name"] = init_json.get("symbolName")
                data["contract_name"] = init_json.get("contractName")
                data["exchange"] = init_json.get("exchange")
                data["last_price"] = init_json.get("lastPrice")
                data["price_change"] = init_json.get("priceChange")
                data["percent_change"] = init_json.get("percentChange")
                data["trade_date"] = init_json.get("tradeTime")
            except json.JSONDecodeError:
                pass

    # Also try extracting from the symbol notes/alerts JSON (has raw numeric values)
    for a_tag in soup.find_all("a", {"data-symbol": True}):
        try:
            sym_data = json.loads(a_tag["data-symbol"])
            raw = sym_data.get("raw", {})
            if raw and raw.get("lastPrice"):
                data["last_price_raw"] = raw.get("lastPrice")
                data["price_change_raw"] = raw.get("priceChange")
                data["percent_change_raw"] = round(raw.get("percentChange", 0) * 100, 2)
                data["daily_last_price"] = raw.get("dailyLastPrice")
                data["point_value"] = sym_data.get("pointValue")
                data["category"] = sym_data.get("category")
                break
        except (json.JSONDecodeError, TypeError):
            continue

    return data

def main():
    try:
        data = scrape_zce_cotton()

        print("\n--- ZCE Cotton No.1 ---")
        print(f"Symbol:         {data['symbol']}")
        print(f"Contract:       {data['contract_name']}")
        print(f"Last Price:     {data['last_price']}")
        print(f"Change:         {data['price_change']} ({data['percent_change']})")
        print(f"Trade Date:     {data['trade_date']}")
        print(f"Exchange:       {data['exchange']}")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"\nData saved to: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
