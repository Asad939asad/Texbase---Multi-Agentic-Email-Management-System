#!/Volumes/ssd2/TEXBASE/venv/bin/python3
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import os
import re

DB_PATH = '/Volumes/ssd2/TEXBASE/USA_ImportYeti/importyeti_data.db'))
BASE_URL = "https://www.importyeti.com"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            country TEXT,
            address TEXT,
            total_shipments TEXT,
            recent_shipment TEXT,
            top_suppliers TEXT,
            profile_url TEXT UNIQUE
        )
    ''')
    conn.commit()
    return conn

def parse_and_store(html, conn):
    soup = BeautifulSoup(html, "html.parser")
    entries = soup.find_all("div", class_="mb-4")
    
    if not entries:
        print("No entries with class 'mb-4' found. Captcha or no results?.")
        return 0
    
    inserted = 0
    cursor = conn.cursor()
    
    for entry in entries:
        try:
            # 1. Company Name and Profile URL
            company_a_tag = entry.find("a", class_=lambda x: x and "text-yeti-info" in x)
            if not company_a_tag:
                company_a_tag = entry.find("a", href=re.compile(r"^/company/"))
            
            if company_a_tag:
                company_name = company_a_tag.get_text(strip=True)
                profile_url = BASE_URL + company_a_tag.get("href", "")
            else:
                continue # Skip if we can't get basic info
                
            # Wait, the user shared HTML has a span with country: <span class="hidden group-hover:block... >United States</span>
            country_span = entry.find("span", class_=lambda x: x and "group-hover:block" in x)
            country = country_span.get_text(strip=True) if country_span else "N/A"
            
            # 2. Address
            address_div = entry.find("div", class_=lambda x: x and "text-yeti-main-dark" in x)
            address = address_div.get_text(separator=" ", strip=True) if address_div else "N/A"
            
            # 3. Total Shipments, Most Recent Shipment, Top Suppliers
            total_shipments = "N/A"
            recent_shipment = "N/A"
            top_suppliers = "N/A"
            
            flex_row = entry.find("div", class_=lambda x: x and "flex-wrap" in x)
            if flex_row:
                blocks = flex_row.find_all("div", class_=lambda x: x and "flex-col" in x, recursive=False)
                for block in blocks:
                    label_div = block.find("div", class_=lambda x: x and "text-yeti-text-3" in x)
                    if not label_div:
                        continue
                    label_text = label_div.get_text(strip=True).lower()
                    
                    # Extract the rest of the text in the block
                    full_text = block.get_text(separator="|", strip=True)
                    parts = full_text.split("|")
                    if len(parts) > 1:
                        val = " ".join(parts[1:]).strip()
                        if "total shipments" in label_text:
                            total_shipments = val
                        elif "most recent shipment" in label_text:
                            recent_shipment = val
                        elif "top suppliers" in label_text:
                            top_suppliers = val
                            
            cursor.execute('''
                INSERT OR IGNORE INTO companies 
                (company_name, country, address, total_shipments, recent_shipment, top_suppliers, profile_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (company_name, country, address, total_shipments, recent_shipment, top_suppliers, profile_url))
            
            if cursor.rowcount > 0:
                inserted += 1
                
        except Exception as e:
            print(f"Error parsing an entry: {e}")
            
    conn.commit()
    return inserted

def scrape_pages(conn):
    # search_query = "%28apparel+%7C+clothing+%7C+garment+%7C+textile+%7C+fabric+%7C+knit+%7C+yarn+%7C+denim+%7C+hosiery+%7C+cotton+%7C+bedding+%7C+%22bed+sheet%22+%7C+towel+%7C+linen+%7C+sportswear+%7C+activewear+%7C+uniform+%7C+workwear+%7C+jacket+%7C+hoodie+%7C+fleece+%7C+terry+%7C+canvas+%7C+leather+%7C+polyester+%7C+%22home+furnishing%22+%7C+upholstery+%7C+curtain+%7C+rug+%7C+carpet%29"
    search_query = "%28apparel+%7C+clothing+%7C+garment+%7C+textile+%7C+fabric+%7C+knit+%7C+yarn+%7C+denim+%7C+hosiery+%7C+cotton+%7C+bedding+%7C+%22bed+sheet%22+%7C+towel+%7C+linen+%7C+sportswear+%7C+activewear+%7C+uniform+%7C+workwear+%7C+jacket+%7C+hoodie+%7C+fleece+%7C+terry+%7C+canvas+%7C+polyester+%29&type=company&shipmentsTotal=2"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        # Iterate to page 200.
        for i in range(564, 801):
            url = f"https://www.importyeti.com/search?q={search_query}&page={i}&type=company"
            print(f"Navigating to page {i}...")
            
            try:
                page.goto(url, timeout=60000)
                # Wait for the results to load
                page.wait_for_selector('div.mb-4', timeout=20000)
                page.wait_for_timeout(2000) # Give it 2s to fully render inner elements
            except Exception as e:
                print(f"Error or timeout loading page {i}: {e}")
                
            html = page.content()
            inserted = parse_and_store(html, conn)
            print(f"Inserted {inserted} companies from page {i}.")

            if i < 1000:
                print("Waiting 60 seconds before fetching the next page...")
                time.sleep(60)

        browser.close()

def main():
    conn = init_db()
    scrape_pages(conn)
    conn.close()

if __name__ == "__main__":
    main()
