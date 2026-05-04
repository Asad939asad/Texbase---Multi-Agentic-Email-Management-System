#!/usr/bin/env python3
"""
Comprehensive Forex & Financial Data scraper.
Sources: investing.com, hamariweb.com, tradingeconomics.com, easydata.sbp.org.pk
Uses Playwright headless for JS-rendered pages, requests for static pages.
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
import json
import os
import re
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'forex_data.json')

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ── investing.com (JS-rendered, needs Playwright) ──────────────────────

INVESTING_PAIRS = {
    "USD_PKR": "https://www.investing.com/currencies/usd-pkr",
    "EUR_PKR": "https://www.investing.com/currencies/eur-pkr",
    "EUR_USD": "https://www.investing.com/currencies/eur-usd",
    "CNY_PKR": "https://www.investing.com/currencies/cny-pkr",
}

def scrape_investing_pairs(page):
    """Scrape currency pairs from investing.com using a shared Playwright page."""
    results = {}
    for label, url in INVESTING_PAIRS.items():
        print(f"  Fetching {label} ...")
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector('[data-test="instrument-price-last"]', timeout=20000)
            time.sleep(1)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            data = {"last_price": None, "change": None, "percent_change": None}
            el = soup.find(attrs={"data-test": "instrument-price-last"})
            if el:
                data["last_price"] = el.get_text(strip=True)
            el = soup.find(attrs={"data-test": "instrument-price-change"})
            if el:
                data["change"] = el.get_text(strip=True)
            el = soup.find(attrs={"data-test": "instrument-price-change-percent"})
            if el:
                data["percent_change"] = el.get_text(strip=True)

            results[label] = data
        except Exception as e:
            print(f"  Error {label}: {e}")
            results[label] = {"error": str(e)}
    return results


def scrape_usdpkr_forwards(page):
    """Scrape USD/PKR forward rates from investing.com."""
    url = "https://www.investing.com/currencies/usd-pkr-forward-rates"
    print(f"  Fetching USD/PKR Forwards ...")
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector("tr[id^='pair_']", timeout=20000)
        time.sleep(1)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        forwards = []
        for tr in soup.find_all("tr", id=re.compile(r'^pair_\d+')):
            cells = tr.find_all("td")
            if len(cells) < 7:
                continue
            name_td = cells[1]
            name = name_td.get_text(strip=True).replace('\xa0', ' ')
            # Only pick 1M-4M forwards
            if "FWD" not in name:
                continue
            bid = cells[2].get_text(strip=True)
            ask = cells[3].get_text(strip=True)
            high = cells[4].get_text(strip=True)
            low = cells[5].get_text(strip=True)
            change = cells[6].get_text(strip=True)
            forwards.append({
                "name": name,
                "bid": bid,
                "ask": ask,
                "high": high,
                "low": low,
                "change": change
            })
        return forwards
    except Exception as e:
        print(f"  Error forwards: {e}")
        return {"error": str(e)}


# ── hamariweb.com Open Market (simple HTTP) ────────────────────────────

def scrape_hamariweb():
    """Scrape open market forex rates from hamariweb.com."""
    url = "https://hamariweb.com/finance/forex/"
    print(f"  Fetching Open Market rates ...")
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        targets = {"usd-to-pkr": "USD_PKR", "eur-to-pkr": "EUR_PKR", "gbp-to-pkr": "GBP_PKR"}
        results = {}

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            for slug, key in targets.items():
                if slug in href:
                    tr = a_tag.find_parent("tr")
                    if tr:
                        tds = tr.find_all("td")
                        if len(tds) >= 3:
                            results[key] = {
                                "buying": tds[1].get_text(strip=True),
                                "selling": tds[2].get_text(strip=True)
                            }
        return results
    except Exception as e:
        print(f"  Error hamariweb: {e}")
        return {"error": str(e)}


# ── tradingeconomics.com (simple HTTP) ─────────────────────────────────

def scrape_tradingeconomics():
    """Scrape Pakistan interest rate, forex reserves, interbank rate."""
    url = "https://tradingeconomics.com/pakistan/interest-rate"
    print(f"  Fetching Pakistan financial indicators ...")
    try:
        headers = {**HTTP_HEADERS, "Accept": "text/html"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results = {}

        # Interest Rate - from the main indicator table
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").lower()
            text = a_tag.get_text(strip=True)
            tr = a_tag.find_parent("tr")
            if not tr:
                continue
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            if "interest-rate" in href and "Interest Rate" in text:
                results["interest_rate"] = {
                    "value": tds[1].get_text(strip=True),
                    "previous": tds[2].get_text(strip=True),
                    "unit": "percent"
                }
            elif "foreign-exchange-reserves" in href:
                results["foreign_exchange_reserves"] = {
                    "value": tds[1].get_text(strip=True),
                    "previous": tds[2].get_text(strip=True),
                    "unit": tds[3].get_text(strip=True) if len(tds) > 3 else "",
                    "date": tds[4].get_text(strip=True) if len(tds) > 4 else ""
                }
            elif "interbank-rate" in href:
                results["interbank_rate"] = {
                    "value": tds[1].get_text(strip=True),
                    "previous": tds[2].get_text(strip=True),
                    "unit": "percent"
                }

        return results
    except Exception as e:
        print(f"  Error tradingeconomics: {e}")
        return {"error": str(e)}


# ── SBP easydata KIBID/KIBOR (simple HTTP) ─────────────────────────────

def scrape_sbp_kibor():
    """Scrape latest KIBID and KIBOR (Six-Months) from SBP easydata."""
    url = "https://easydata.sbp.org.pk/apex/f?p=10:211:4932927851621::NO:RP:P211_DATASET_TYPE_CODE,P211_PAGE_ID:TS_GP_BAM_SIRKIBOR_D,1&cs=1883CA5742C889BB27CD0C1C818F1AB8B"
    print(f"  Fetching KIBID/KIBOR ...")
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=15, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results = {}

        # Get the latest date from the last header column
        latest_date = None
        header_row = soup.find("tr", attrs={"class": None})
        for th in soup.find_all("th", class_="t20ReportHeader"):
            th_id = th.get("id", "")
            if re.match(r'\d{2}-\w{3}-\d{4}', th_id):
                latest_date = th_id  # keep overwriting, last one is the latest

        for tr in soup.find_all("tr", class_="highlight-row"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue

            series_name = ""
            for td in tds:
                text = td.get_text(strip=True)
                if "Six-Months Karachi Interbank" in text:
                    series_name = text
                    break

            if not series_name:
                continue

            # Get the value from the LAST td that contains a span with a number
            last_value = None
            for td in reversed(tds):
                span = td.find("span")
                if span:
                    val = span.get_text(strip=True)
                    try:
                        last_value = float(val)
                        break
                    except ValueError:
                        continue

            if "Bid" in series_name:
                results["KIBID_6M"] = {"name": series_name, "latest_date": latest_date, "latest_value": last_value}
            elif "Offer" in series_name:
                results["KIBOR_6M"] = {"name": series_name, "latest_date": latest_date, "latest_value": last_value}

        return results
    except Exception as e:
        print(f"  Error SBP: {e}")
        return {"error": str(e)}


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Forex & Financial Data Scraper")
    print("=" * 50)

    all_data = {"scraped_at": datetime.now().isoformat()}

    # 1. investing.com pairs + forwards (Playwright headless)
    print("\n[1/4] investing.com (Playwright headless)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = context.new_page()

        all_data["investing_pairs"] = scrape_investing_pairs(page)
        all_data["usdpkr_forwards"] = scrape_usdpkr_forwards(page)

        browser.close()

    # 2. hamariweb Open Market
    print("\n[2/4] hamariweb.com Open Market rates")
    all_data["open_market"] = scrape_hamariweb()

    # 3. tradingeconomics Pakistan
    print("\n[3/4] tradingeconomics.com Pakistan indicators")
    all_data["pakistan_indicators"] = scrape_tradingeconomics()

    # 4. SBP KIBID/KIBOR
    print("\n[4/4] SBP easydata KIBID/KIBOR")
    all_data["kibid_kibor"] = scrape_sbp_kibor()

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)

    print(f"\n{'=' * 50}")
    print(f"All data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
