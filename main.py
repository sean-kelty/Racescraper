import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
STATE = "nc"
MAX_PAGES = 3
OUTPUT_FILE = "nc_races_cached.csv"
WAIT_TIMEOUT = 20

# --- PART 1: SETUP STEALTH SELENIUM ---
def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# --- PART 2: SMART URL RESOLVER ---
def resolve_redirect_selenium(driver, link_element):
    original_window = driver.current_window_handle
    try:
        url_to_visit = link_element.get_attribute("href")
        driver.execute_script("window.open(arguments[0], '_blank');", url_to_visit)
        
        WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(2))
        windows = driver.window_handles
        new_window = [w for w in windows if w != original_window][0]
        driver.switch_to.window(new_window)
        
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                lambda d: "click.pl" not in d.current_url and d.current_url != "about:blank"
            )
            final_url = driver.current_url
        except:
            final_url = driver.current_url

        driver.close()
        driver.switch_to.window(original_window)
        return final_url

    except Exception:
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to.window(original_window)
        return "Error Resolving"

# --- PART 3: MAIN SCRAPER ---
def scrape_races():
    driver = setup_driver()
    results = []
    
    # --- CACHE INITIALIZATION ---
    # This dictionary stores: { "internal_url": "final_destination_url" }
    link_cache = {} 
    
    print(f"Starting Scrape for {STATE.upper()} with Caching enabled...")

    try:
        for page_num in range(1, MAX_PAGES + 1):
            url = f"https://www.runningintheusa.com/classic/list/{STATE}/upcoming/page-{page_num}"
            print(f"Processing Page {page_num}...")
            
            driver.get(url)
            
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".index-race-row"))
                )
            except:
                print("   -> Timed out waiting for rows. Skipping page.")
                continue

            rows = driver.find_elements(By.CSS_SELECTOR, ".index-race-row")
            
            for i, row in enumerate(rows):
                try:
                    # Refresh element reference
                    current_row = driver.find_elements(By.CSS_SELECTOR, ".index-race-row")[i]
                    
                    race_name = current_row.find_element(By.TAG_NAME, "h3").text.strip()
                    full_text = current_row.text
                    
                    # Parsing
                    lines = full_text.split('\n')
                    location_text = next((line for line in lines if f", {STATE.upper()}" in line), "Unknown")
                    city = location_text.split(',')[0].strip()
                    
                    distances = "Unknown"
                    for line in lines:
                        if any(x in line for x in ['5K', '10K', 'Marathon', '1M', '13.1']):
                            distances = line
                            break
                    
                    is_virtual = "Yes" if "Virtual" in full_text else "No"
                    is_trail = "Yes" if "Trail" in full_text else "No"

                    # --- CACHED RESOLUTION LOGIC ---
                    real_website = "N/A"
                    try:
                        link_el = current_row.find_element(By.PARTIAL_LINK_TEXT, "More Information")
                        
                        # 1. Get the internal link string (e.g. ".../click.pl?id=555")
                        internal_link = link_el.get_attribute("href")
                        
                        if is_virtual == "No":
                            # 2. Check the Cache
                            if internal_link in link_cache:
                                real_website = link_cache[internal_link]
                                print(f"   -> [CACHE HIT] Used saved link for: {race_name}")
                            else:
                                # 3. Not in cache? Resolve it and save it.
                                print(f"   -> Resolving URL for: {race_name}...", end="", flush=True)
                                resolved_url = resolve_redirect_selenium(driver, link_el)
                                
                                # Save to cache
                                link_cache[internal_link] = resolved_url
                                real_website = resolved_url
                                print(f" Done! ({real_website})")
                        else:
                            real_website = "Virtual Race Link"
                            
                    except Exception:
                        pass 

                    results.append([race_name, city, STATE.upper(), distances, is_trail, is_virtual, real_website])

                except Exception as e:
                    print(f"   -> Skipped a row due to error: {e}")
                    continue

    finally:
        driver.quit()

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "City", "State", "Distance", "Is Trail?", "Is Virtual?", "Website"])
        writer.writerows(results)
    
    print(f"\nDone! Scraped {len(results)} races.")

if __name__ == "__main__":
    scrape_races()
