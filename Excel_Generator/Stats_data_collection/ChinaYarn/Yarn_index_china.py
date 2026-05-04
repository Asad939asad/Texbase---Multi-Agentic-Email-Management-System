#!/usr/bin/env python3
"""
ZCE Cotton Yarn index scraper from investing.com.
Uses Playwright headless (no visible window) since page is JS-rendered.
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import os
import time

URL = "https://www.investing.com/commodities/zce-cotton-yarn-futures"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'yarn_index_china.json')

def scrape_yarn_index():
    print(f"Fetching ZCE Cotton Yarn data from: {URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(URL, timeout=30000)
            page.wait_for_selector('[data-test="instrument-price-last"]', timeout=15000)
            time.sleep(2)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")

    data = {
        "symbol": "CCYc1",
        "name": "ZCE Cotton Yarn",
        "exchange": "ZCE",
        "currency": "CNY",
        "last_price": None,
        "price_change": None,
        "percent_change": None,
        "days_range_low": None,
        "days_range_high": None,
        "week52_range_low": None,
        "week52_range_high": None,
        "trading_state": None,
        "trade_date": None
    }

    # Last price
    el = soup.find(attrs={"data-test": "instrument-price-last"})
    if el:
        data["last_price"] = el.get_text(strip=True)

    # Price change
    el = soup.find(attrs={"data-test": "instrument-price-change"})
    if el:
        data["price_change"] = el.get_text(strip=True)

    # Percent change
    el = soup.find(attrs={"data-test": "instrument-price-change-percent"})
    if el:
        data["percent_change"] = el.get_text(strip=True)

    # Trading state
    el = soup.find(attrs={"data-test": "trading-state-label"})
    if el:
        data["trading_state"] = el.get_text(strip=True)

    # Trade date
    el = soup.find(attrs={"data-test": "trading-time-label"})
    if el:
        data["trade_date"] = el.get_text(strip=True)

    # Day's Range & 52wk Range from the range sections
    range_sections = soup.find_all("div", class_="text-secondary")
    for sec in range_sections:
        label = sec.get_text(strip=True)
        parent = sec.find_parent()
        if parent:
            bold_spans = parent.find_all("span", class_=None)
            values = [s.get_text(strip=True) for s in bold_spans if s.get_text(strip=True).replace(",", "").replace(".", "").isdigit()]
            if len(values) >= 2:
                if "Day" in label:
                    data["days_range_low"] = values[0]
                    data["days_range_high"] = values[1]
                elif "52" in label:
                    data["week52_range_low"] = values[0]
                    data["week52_range_high"] = values[1]

    return data

def main():
    try:
        data = scrape_yarn_index()

        print("\n--- ZCE Cotton Yarn ---")
        print(f"Last Price:     {data['last_price']}")
        print(f"Change:         {data['price_change']} {data['percent_change']}")
        print(f"Day's Range:    {data['days_range_low']} - {data['days_range_high']}")
        print(f"52wk Range:     {data['week52_range_low']} - {data['week52_range_high']}")
        print(f"Status:         {data['trading_state']} ({data['trade_date']})")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"\nData saved to: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
