    import time
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
STATE = "nc"
MAX_PAGES = 3
OUTPUT_FILE = "nc_races_nuclear.csv"
WAIT_TIMEOUT = 20

def setup_driver():
    # undetected-chromedriver works best when you DON'T touch too many options.
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Note: We do NOT add '--headless' here. We will handle that in the workflow file.
    # This allows the browser to think it is visible, which bypasses detection.
    
    driver = uc.Chrome(options=options, version_main=None) 
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
    print("Initializing Undetected Chrome...")
    driver = setup_driver()
    results = []
    link_cache = {} 

    try:
        for page_num in range(1, MAX_PAGES + 1):
            url = f"https://www.runningintheusa.com/classic/list/{STATE}/upcoming/page-{page_num}"
            print(f"Scraping Page {page_num}: {url}")
            
            driver.get(url)
            
            # Wait longer for the initial check (Cloudflare often takes 5-10s to verify)
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".index-race-row"))
                )
            except:
                print("   -> Timed out waiting for rows. Checking page source for errors...")
                # Debugging: print a snippet of the page to see if we were blocked
                print(driver.page_source[:500])
                continue

            rows = driver.find_elements(By.CSS_SELECTOR, ".index-race-row")
            print(f"   -> Found {len(rows)} races.")
            
            for i, row in enumerate(rows):
                try:
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

    finally:
        driver.quit()

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "City", "State", "Distance", "Is Trail?", "Is Virtual?", "Website"])
        writer.writerows(results)
    print(f"Saved {len(results)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_races()
