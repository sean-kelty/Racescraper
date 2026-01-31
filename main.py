import time
import csv
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
STATE = "nc"
MAX_PAGES = 3
OUTPUT_FILE = "nc_races_stealth.csv"
WAIT_TIMEOUT = 10

def setup_driver():
    options = Options()
    # Standard headless arguments for stability
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # MANAGER: This downloads the correct driver automatically
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=options)

    # STEALTH: Apply the mask
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver

def resolve_redirect(driver, link_element):
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
    except:
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to.window(original_window)
        return "N/A"

def scrape_races():
    print("Initializing Scraper...")
    results = []
    driver = None
    
    try:
        driver = setup_driver()
        link_cache = {} 

        for page_num in range(1, MAX_PAGES + 1):
            url = f"https://www.runningintheusa.com/classic/list/{STATE}/upcoming/page-{page_num}"
            print(f"Scraping Page {page_num}: {url}")
            
            driver.get(url)
            
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".index-race-row"))
                )
            except:
                print("   -> Page load timed out or blocked.")
                continue

            rows = driver.find_elements(By.CSS_SELECTOR, ".index-race-row")
            print(f"   -> Found {len(rows)} races.")
            
            for i, row in enumerate(rows):
                try:
                    # Refresh the element to avoid stale reference
                    current_row = driver.find_elements(By.CSS_SELECTOR, ".index-race-row")[i]
                    
                    race_name = current_row.find_element(By.TAG_NAME, "h3").text.strip()
                    full_text = current_row.text
                    
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
                    
                    real_website = "N/A"
                    if is_virtual == "No":
                        try:
                            link_el = current_row.find_element(By.PARTIAL_LINK_TEXT, "More Information")
                            internal_link = link_el.get_attribute("href")
                            
                            if internal_link in link_cache:
                                real_website = link_cache[internal_link]
                            else:
                                real_website = resolve_redirect(driver, link_el)
                                link_cache[internal_link] = real_website
                        except:
                            pass
                    
                    results.append([race_name, city, STATE.upper(), distances, is_trail, is_virtual, real_website])
                except Exception as e:
                    continue

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    
    finally:
        if driver:
            driver.quit()

    # Always write the CSV, even if empty, so the artifact uploads (prevents "No Artifact" error)
    print(f"Writing {len(results)} rows to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "City", "State", "Distance", "Is Trail?", "Is Virtual?", "Website"])
        writer.writerows(results)
    print("Done.")

if __name__ == "__main__":
    scrape_races()
