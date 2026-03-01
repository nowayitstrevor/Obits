"""
Enhanced obituary scraper with Selenium fallback.

This script tries the original requests approach first, and if that doesn't find
any obituaries or fails, it falls back to using Selenium to render JavaScript.
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

# Try to import Selenium components, but don't fail if they're not available
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not available, will use requests-only approach")


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


def fetch_obituaries_requests() -> List[Obituary]:
    """Fetch obituaries using simple HTTP requests."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
    }
    response = requests.get(BASE_URL, headers=headers, timeout=30)
    response.raise_for_status()
    return parse_obituaries(response.text)


def fetch_obituaries_selenium() -> List[Obituary]:
    """Fetch obituaries using Selenium for JavaScript rendering."""
    if not SELENIUM_AVAILABLE:
        return []
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None
    try:
        print("Setting up Chrome driver for JavaScript rendering...")
        driver = webdriver.Chrome(
            service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, 10)
        
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/obituaries/')]")))
            print("JavaScript content loaded successfully")
        except:
            print("Continuing without waiting for JavaScript...")
        
        time.sleep(2)
        page_source = driver.page_source
        return parse_obituaries(page_source)
        
    except Exception as e:
        print(f"Selenium failed: {e}")
        return []
    finally:
        if driver:
            driver.quit()


def parse_obituaries(html_content: str) -> List[Obituary]:
    """Parse obituaries from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    obituaries: List[Obituary] = []
    obid_re = re.compile(r"obId=(\d+)")
    
    anchors = soup.find_all("a", href=True)
    print(f"Found {len(anchors)} anchor tags to examine")
    
    for anchor in anchors:
        href = anchor.get("href")
        if not href or "/obituaries/" not in href:
            continue
            
        m = obid_re.search(href)
        if not m:
            continue
            
        ob_id = m.group(1)
        name = anchor.get_text(strip=True)
        url = href if href.startswith("http") else f"https://www.lakeshorefuneralhome.com{href}"
        
        # Find date range
        date_range = ""
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
    
    # Deduplicate
    unique: Dict[str, Obituary] = {}
    for ob in obituaries:
        unique.setdefault(ob.ob_id, ob)
    
    return list(unique.values())


def fetch_obituaries() -> List[Obituary]:
    """Fetch obituaries with fallback strategy."""
    print("Trying requests approach first...")
    
    try:
        obituaries = fetch_obituaries_requests()
        if obituaries:
            print(f"Requests approach successful: found {len(obituaries)} obituaries")
            return obituaries
        else:
            print("Requests approach found no obituaries")
    except Exception as e:
        print(f"Requests approach failed: {e}")
    
    # Fall back to Selenium if available
    if SELENIUM_AVAILABLE:
        print("Falling back to Selenium approach...")
        try:
            obituaries = fetch_obituaries_selenium()
            if obituaries:
                print(f"Selenium approach successful: found {len(obituaries)} obituaries")
                return obituaries
            else:
                print("Selenium approach found no obituaries")
        except Exception as e:
            print(f"Selenium approach failed: {e}")
    
    print("Both approaches failed or found no obituaries")
    return []


def load_seen(file_path: str) -> Set[str]:
    """Load previously seen obituary IDs from file."""
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("seen_ids", []))
    except Exception:
        return set()


def save_seen(file_path: str, seen_ids: Set[str]) -> None:
    """Save seen obituary IDs to file."""
    payload = {"seen_ids": sorted(seen_ids)}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    """Main script entry point."""
    print(f"Fetching obituary listings from {BASE_URL}...")
    
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

    save_seen(STORAGE_FILE, seen_ids)


if __name__ == "__main__":
    main()
