#!/usr/bin/env python3
"""
Pakistan yarn prices scraper from yarnonline.pk.
Uses Playwright headless (no visible window) because the table is JS-rendered.
Scrapes 4 yarn quality pages and saves rate_per_10lbs to JSON.
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import os
import re
import time

URLS = {
    "20S Cotton": "https://yarnonline.pk/?spinning_mills=&yarn_quality=20S+Cotton&blend_by=",
    "30S Cotton": "https://yarnonline.pk/?spinning_mills=&yarn_quality=30S+Cotton&blend_by=",
    "40 CF Cotton": "https://yarnonline.pk/?spinning_mills=&yarn_quality=40+CF+COTTON&blend_by=",
    "60 CF Cotton": "https://yarnonline.pk/?spinning_mills=&yarn_quality=60+CF+COTTON&blend_by="
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'yarn_prices.json')

def scrape_all():
    print("Scraping yarn prices from yarnonline.pk (headless browser)")
    all_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()

        for label, url in URLS.items():
            print(f"  Fetching: {label} ...")
            try:
                page.goto(url, timeout=30000)
                # Wait for DataTables to populate the tbody
                page.wait_for_selector("#dataTables tbody tr", timeout=15000)
                time.sleep(1)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                table = soup.find("table", id="dataTables")
                if not table:
                    print(f"  Warning: No table found for {label}")
                    all_data[label] = []
                    continue

                tbody = table.find("tbody")
                if not tbody:
                    all_data[label] = []
                    continue

                rates = []
                for tr in tbody.find_all("tr"):
                    cells = tr.find_all("td")
                    if len(cells) < 8:
                        continue

                    last_updated = cells[7].get_text(strip=True)
                    if "Feb 2026" not in last_updated:
                        continue

                    rate_text = cells[4].get_text(strip=True)
                    rate_text = re.sub(r'\+\s*Gst', '', rate_text).strip()
                    rates.append(rate_text)

                all_data[label] = rates
                print(f"  Found {len(rates)} entries for {label}")

            except Exception as e:
                print(f"  Error scraping {label}: {e}")
                all_data[label] = []

        browser.close()

    return all_data

def main():
    data = scrape_all()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    total = sum(len(v) for v in data.values())
    print(f"\nTotal {total} entries saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
