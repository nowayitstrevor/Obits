"""
Script to fetch and track newly‑listed obituaries from Lake Shore Funeral Home using Selenium.

This module will download the first page of the obituary listings from
https://www.lakeshorefuneralhome.com/obituaries/obituary-listings and parse
out the individual obituaries using a headless Chrome browser.  Each obituary 
link on the page includes an `obId` query parameter which uniquely identifies 
that notice.  The script keeps a record of previously seen obituaries in a 
local JSON file and will print out any newly discovered entries when run.  
At the end of a run it updates the record of seen items so that subsequent 
runs only report obituaries that have appeared since the last execution.

Usage::

    python scrape_obituaries_selenium.py

Running the script regularly (e.g. via cron or a task scheduler) will
continuously monitor the site for new listings.  If desired, you can modify
the behaviour in `main()` to do something more sophisticated with newly
found obituaries, such as sending an email or writing to a database.

Dependencies:

* requests
* beautifulsoup4
* selenium
* webdriver-manager

Install them via pip if necessary::

    pip install requests beautifulsoup4 selenium webdriver-manager

Note: This script uses Selenium with a headless Chrome browser to render the
page and wait for JavaScript content to load before parsing the HTML.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Set

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


BASE_URL = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"
STORAGE_FILE = "seen_obituaries.json"


@dataclass
class Obituary:
    """A simple container for obituary metadata."""

    ob_id: str
    name: str
    url: str
    date_range: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "ob_id": self.ob_id,
            "name": self.name,
            "url": self.url,
            "date_range": self.date_range,
        }


def fetch_obituaries() -> List[Obituary]:
    """Download the listing page and extract obituary entries using Selenium.

    Returns a list of ``Obituary`` objects.  The function uses a headless Chrome
    browser to render the page and wait for JavaScript content to load, then
    looks for anchor elements whose ``href`` contains ``/obituaries/`` and an 
    ``obId=`` query parameter.  It also tries to extract the date range 
    associated with each listing by looking for a sibling element containing 
    a dash (e.g. ``Mar 06, 1947 – Jul 22, 2025``).
    """
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Add a realistic user agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None
    page_source = ""
    
    try:
        print("Setting up Chrome driver...")
        # Initialize the Chrome driver with automatic driver management
        driver = webdriver.Chrome(
            service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        print("Chrome driver initialized successfully")
        
        # Navigate to the page
        print(f"Loading page: {BASE_URL}")
        driver.get(BASE_URL)
        print("Page loaded successfully")
        
        # Wait for the page to load and content to be populated
        # We'll wait for obituary links to appear or timeout after 10 seconds
        wait = WebDriverWait(driver, 10)
        
        # Try to wait for obituary content to load
        # Look for elements that would contain obituary links
        try:
            # Wait for any anchor tag with href containing "obituaries" to appear
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/obituaries/')]")))
            print("Obituary content detected, proceeding with parsing...")
        except:
            print("No obituary links found after waiting, proceeding anyway...")
        
        # Give a small additional wait for any remaining JavaScript
        time.sleep(2)
        
        # Get the page source after JavaScript has executed
        page_source = driver.page_source
        print(f"Retrieved page source ({len(page_source)} characters)")
        
    except Exception as e:
        print(f"Error during browser automation: {e}")
        # Fall back to a simple requests approach if Selenium fails
        print("Falling back to simple HTTP request...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(BASE_URL, headers=headers, timeout=30)
            response.raise_for_status()
            page_source = response.text
            print(f"Fallback successful, got {len(page_source)} characters")
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return []
        
    finally:
        # Always close the driver
        if driver:
            driver.quit()
            print("Browser closed")
    
    # Parse the rendered HTML with BeautifulSoup
    soup = BeautifulSoup(page_source, "html.parser")
    
    obituaries: List[Obituary] = []
    
    # Regular expression to pull out the obId from the query string
    obid_re = re.compile(r"obId=(\d+)")
    
    # Find all anchor tags linking to individual obituaries
    anchors = soup.find_all("a", href=True)
    print(f"Found {len(anchors)} anchor tags to examine")
    
    for anchor in anchors:
        href = anchor.get("href")
        if not href:
            continue
        # We're only interested in obituary links that include an obId parameter
        if "/obituaries/" not in href:
            continue
        m = obid_re.search(href)
        if not m:
            continue
        ob_id = m.group(1)
        # Extract the displayed name from the anchor
        name = anchor.get_text(strip=True)
        # Derive the absolute URL if necessary
        url = href if href.startswith("http") else f"https://www.lakeshorefuneralhome.com{href}"

        # Attempt to find the associated date range.  Typically this is within
        # the same card or a sibling element.  We look for the nearest <p>
        # containing a dash (– or -) in its text.
        date_range = ""
        # First, search within the next siblings of the anchor's parent
        parent = anchor.parent
        if parent:
            p_tags = parent.find_all_next("p", limit=3)
            for p in p_tags:
                text = p.get_text(strip=True)
                if "-" in text or "–" in text:
                    date_range = text
                    break
        obituaries.append(Obituary(ob_id=ob_id, name=name, url=url, date_range=date_range))
        print(f"Found obituary: {name} (ID: {ob_id})")

    # Deduplicate by ob_id in case the same obituary appears multiple times
    unique: Dict[str, Obituary] = {}
    for ob in obituaries:
        unique.setdefault(ob.ob_id, ob)

    print(f"Found {len(unique)} unique obituaries")
    return list(unique.values())


def load_seen(file_path: str) -> Set[str]:
    """Load previously seen obituary IDs from ``file_path``.

    Returns an empty set if the file does not exist or is empty.
    """
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("seen_ids", []))
    except Exception:
        # Corrupted file; start fresh
        return set()


def save_seen(file_path: str, seen_ids: Set[str]) -> None:
    """Save the set of seen obituary IDs to ``file_path``."""
    payload = {"seen_ids": sorted(seen_ids)}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    """Entry point for command line invocation.

    Fetch the current obituaries from the website, compare against the stored
    IDs, and print out any new entries.  At the end of the run the known IDs
    are updated.
    """
    print(f"Fetching obituary listings from {BASE_URL}…")
    try:
        current_obits = fetch_obituaries()
    except Exception as e:
        print(f"Failed to fetch obituaries: {e}")
        sys.exit(1)

    seen_ids = load_seen(STORAGE_FILE)
    new_obits = [ob for ob in current_obits if ob.ob_id not in seen_ids]

    if new_obits:
        print(f"Found {len(new_obits)} new obituary{'s' if len(new_obits) != 1 else ''}:")
        for ob in new_obits:
            print(f"- {ob.name} ({ob.date_range}) → {ob.url}")
            seen_ids.add(ob.ob_id)
    else:
        print("No new obituaries since last run.")

    # Update the seen list regardless of whether any were found
    save_seen(STORAGE_FILE, seen_ids)


if __name__ == "__main__":
    main()
