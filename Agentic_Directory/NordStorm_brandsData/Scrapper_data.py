"""
Nordstrom Brands List Scraper
Extracts brand names and their links from the Nordstrom brands list page.
Uses Playwright with stealth settings to bypass bot detection.
"""

import json
import os
import time
from playwright.sync_api import sync_playwright


BASE_URL = "https://www.nordstrom.com"
TARGET_URL = "https://www.nordstrom.com/brands-list/men/clothing?breadcrumb=Home%2FBrands%20List%2FMen%2FClothing"
OUTPUT_FILE = '/Volumes/ssd2/TEXBASE/Agentic_Directory/NordStorm_brandsData/nordstrom_brands.json'))


def load_existing_brands(filename):
    """Load existing brands from JSON file if it exists."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[*] Loaded {len(data)} existing brands from {filename}")
            return data
    return []


def scrape_brands():
    """Scrape all brand names and links from the Nordstrom brands list page."""
    brands = []

    with sync_playwright() as p:
        # Launch browser (non-headless is more reliable for bot detection)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        try:
            print(f"[*] Loading page: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for brand links to appear
            print("[*] Waiting for brand elements to load...")
            page.wait_for_selector("a.dxPxF", timeout=20000)

            # Scroll to the bottom to trigger lazy-loaded content
            print("[*] Scrolling page to load all sections...")
            prev_height = 0
            while True:
                curr_height = page.evaluate("document.body.scrollHeight")
                if curr_height == prev_height:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                prev_height = curr_height

            # Extra wait after scrolling
            page.wait_for_timeout(2000)

            # Extract brand data using page.evaluate for speed
            brands = page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a.dxPxF');
                    return Array.from(links).map(a => {
                        const span = a.querySelector('span');
                        return {
                            brand_name: span ? span.textContent.trim() : a.textContent.trim(),
                            link: a.href
                        };
                    });
                }
            """)

            print(f"[*] Found {len(brands)} brand entries on page")

        except Exception as e:
            print(f"[!] Error during scraping: {e}")
        finally:
            browser.close()

    return brands


def merge_brands(existing, new_brands):
    """Merge new brands into existing list, skipping duplicates by brand_name."""
    existing_names = {b["brand_name"] for b in existing}
    added = []

    for brand in new_brands:
        if brand["brand_name"] not in existing_names:
            existing.append(brand)
            existing_names.add(brand["brand_name"])
            added.append(brand["brand_name"])

    return existing, added


def save_to_json(data, filename):
    """Save data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Saved {len(data)} total brands to {filename}")


def main():
    # Load existing brands from JSON (if any)
    existing_brands = load_existing_brands(OUTPUT_FILE)

    # Scrape new brands
    new_brands = scrape_brands()

    if new_brands:
        # Merge: only add unique brands
        merged, added = merge_brands(existing_brands, new_brands)

        save_to_json(merged, OUTPUT_FILE)

        print(f"\n[✓] {len(added)} new unique brands added")
        if added:
            print(f"--- New brands added (first 10) ---")
            for name in added[:10]:
                print(f"  + {name}")
            if len(added) > 10:
                print(f"  ... and {len(added) - 10} more")

        print(f"[✓] Total brands in file: {len(merged)}")
    else:
        print("[!] No brands were scraped. The page might have changed or blocked the request.")


if __name__ == "__main__":
    main()
