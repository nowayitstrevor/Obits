"""
Script to fetch and track newly‑listed obituaries from Lake Shore Funeral Home.

This module will download the first page of the obituary listings from
https://www.lakeshorefuneralhome.com/obituaries/obituary-listings and parse
out the individual obituaries.  Each obituary link on the page includes an
`obId` query parameter which uniquely identifies that notice.  The script
keeps a record of previously seen obituaries in a local JSON file and will
print out any newly discovered entries when run.  At the end of a run it
updates the record of seen items so that subsequent runs only report
obituaries that have appeared since the last execution.

Usage::

    python scrape_obituaries.py

Running the script regularly (e.g. via cron or a task scheduler) will
continuously monitor the site for new listings.  If desired, you can modify
the behaviour in `main()` to do something more sophisticated with newly
found obituaries, such as sending an email or writing to a database.

Dependencies:

* requests
* beautifulsoup4

Install them via pip if necessary::

    pip install requests beautifulsoup4

Note: the funeral home website loads much of its content via JavaScript.
In practice, the static HTML still contains anchor tags with the obituary
links (including the `obId` parameter) which can be parsed without a full
browser.  If the site structure changes or if you find this script isn't
capturing new listings, consider switching to a headless browser such as
Selenium or Playwright.
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Set

import requests
from bs4 import BeautifulSoup


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
    """Download the listing page and extract obituary entries.

    Returns a list of ``Obituary`` objects.  The function looks for anchor
    elements whose ``href`` contains ``/obituaries/`` and an ``obId=`` query
    parameter.  It also tries to extract the date range associated with each
    listing by looking for a sibling element containing a dash (e.g.
    ``Mar 06, 1947 – Jul 22, 2025``).
    """
    headers = {
        # Pretend to be a browser.  Some sites block generic Python user agents.
        "User-Agent": (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0"
        ),
    }
    response = requests.get(BASE_URL, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    obituaries: List[Obituary] = []

    # Regular expression to pull out the obId from the query string
    obid_re = re.compile(r"obId=(\d+)")

    # Find all anchor tags linking to individual obituaries
    anchors = soup.find_all("a", href=True)
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

    # Deduplicate by ob_id in case the same obituary appears multiple times
    unique: Dict[str, Obituary] = {}
    for ob in obituaries:
        unique.setdefault(ob.ob_id, ob)

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
