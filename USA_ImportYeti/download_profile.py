from playwright.sync_api import sync_playwright
import time
url = "https://www.importyeti.com/company/textile-fabric-associates"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto(url, timeout=60000)
    for _ in range(5):
        page.evaluate("window.scrollBy(0, window.innerHeight);")
        time.sleep(1)
    page.wait_for_timeout(3000)
    with open("profile_debug_2.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    browser.close()
