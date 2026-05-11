#!/Volumes/ssd2/TEXBASE/venv/bin/python3
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import os

# --- CONFIGURATION ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'importyeti_data.db')
TARGET_URL = "https://www.importyeti.com/company/world-textile-sourcing"  # <--- LINK TO SCRAP
# ---------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            profile_url TEXT UNIQUE,
            location_info TEXT,
            hs_codes TEXT
        )
    ''')
    conn.commit()
    return conn

def parse_data(html):
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Location Info
    location_info = "N/A"
    location_svg = soup.find("svg", class_=lambda x: x and "fa-location-dot" in x)
    if location_svg:
        location_div = location_svg.find_parent("div", class_=lambda x: x and "flex-col" in x)
        if location_div:
            location_info = location_div.get_text(separator=" | ", strip=True)

    # 2. HS Codes from Treemap
    hs_codes = "N/A"
    treemap_groups = soup.find_all("g", class_=lambda x: x and "treemap_groupd3-treemap" in x)
    
    if treemap_groups:
        texts = []
        for g in treemap_groups:
            tspans = g.find_all("tspan")
            group_texts = [t.get_text(strip=True) for t in tspans if t.get_text(strip=True)]
            if group_texts:
                texts.append(" ".join(group_texts))
                
        if texts:
            unique_texts = []
            for t in texts:
                if t not in unique_texts:
                    unique_texts.append(t)
            hs_codes = " | ".join(unique_texts)
            
    return location_info, hs_codes

def save_to_db(conn, url, location, hs_codes):
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO company_profiles 
            (company_id, profile_url, location_info, hs_codes)
            VALUES (?, ?, ?, ?)
        ''', (None, url, location, hs_codes))
        conn.commit()
        print(f"Success: Data saved to DB for {url}")
    except Exception as e:
        print(f"DB Error: {e}")

def scrape_single_link(url):
    print(f"Starting scrape for: {url}")
    
    # Fix for MacOS EPERM/Temp dir issues with Playwright
    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".playwright_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ["TMPDIR"] = tmp_dir
    
    with sync_playwright() as p:
        # CHANGED: headless=True makes it run without opening a visible window
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=60000)
            
            # Wait for specific element to ensure load
            try:
                page.wait_for_selector('svg.fa-location-dot', timeout=15000)
            except:
                print("Warning: Location icon not found, page might be incomplete.")

            # Scroll loop to trigger lazy-loaded elements (D3 Treemap)
            print("Scrolling to trigger visualizations...")
            for _ in range(8):
                page.evaluate("window.scrollBy(0, 500);")
                time.sleep(0.5)
            
            # Extra wait for D3 animation
            time.sleep(2)
            
            html = page.content()
            return html
            
        except Exception as e:
            print(f"Scraping Error: {e}")
            return None
        finally:
            browser.close()

def main():
    # 1. Init Database
    conn = init_db()
    
    # 2. Scrape the specific link
    html = scrape_single_link(TARGET_URL)
    
    if html:
        # 3. Parse Data
        loc, codes = parse_data(html)
        
        # 4. Show Results
        print("\n--- SCRAPED DATA ---")
        print(f"URL:      {TARGET_URL}")
        print(f"Location: {loc}")
        print(f"HS Codes: {codes[:100]}..." if len(codes) > 100 else f"HS Codes: {codes}")
        
        # 5. Save
        save_to_db(conn, TARGET_URL, loc, codes)
    else:
        print("Failed to retrieve HTML.")
        
    conn.close()

if __name__ == "__main__":
    main()