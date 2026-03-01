"""
Aggregate obituaries from multiple funeral home websites in the Waco, TX area.

This script demonstrates how to pull obituary information from several
independent funeral home websites and produce a consolidated list sorted by
the date of death.  Each entry in the consolidated list contains the
decedent’s name, birth date, death date, and a URL to the obituary.  You can
extend this script by adding new scraping functions for additional sites.

Currently implemented scrapers:

* Lake Shore Funeral Home (`lakeshorefuneralhome.com`) – uses the same logic
  defined in ``scrape_obituaries.py`` to extract new obituaries from the
  obituary listings page.  It returns all obituaries on page 1 along with
  their date ranges.
* Robertson Funeral and Cremation (`robertsonfh.com`) – parses the all
  obituaries listing and follows each “View” link to retrieve the official
  obituary page.  The birth and death dates are extracted from the heading
  line in the format “BirthDate ~ DeathDate (age #)” if present.

Many of the other funeral homes listed by the user (e.g. Grace Gardens, Aderhold,
McDowell, Pecan Grove) load their obituary listings dynamically with
JavaScript.  To handle those sites you will likely need to employ a
headless browser (e.g. Selenium or Playwright) to render the page before
parsing it.  See the ``scrape_lakeshore()`` function for an example of using
requests + BeautifulSoup on a static page; replace it with a Selenium-based
approach if necessary.

Usage::

    python aggregate_obituaries.py

Dependencies:

* requests
* beautifulsoup4

Install them via pip if necessary::

    pip install requests beautifulsoup4

If you add Selenium-based scrapers you will also need::

    pip install selenium webdriver-manager

Note: Running this script will send HTTP GET requests to the target
websites.  Please respect the sites’ terms of service and robots.txt
policies.  Do not scrape more frequently than necessary.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup


###############################################################################
# Data structures
###############################################################################


@dataclass
class ObituaryRecord:
    """Represents a single obituary entry across funeral homes."""

    name: str
    birth_date: Optional[_dt.date]
    death_date: Optional[_dt.date]
    url: str
    source: str  # The funeral home domain

    def date_key(self) -> _dt.date:
        """Return a date for sorting; fall back to a very early date if unknown."""
        return self.death_date or _dt.date(1900, 1, 1)


###############################################################################
# Utility functions
###############################################################################


def parse_date(date_str: str) -> Optional[_dt.date]:
    """Parse a date string of the form "Month DD, YYYY" into a ``datetime.date``.

    Returns ``None`` if the string cannot be parsed.  This helper is tolerant
    of irregular spacing and capitalization.
    """
    try:
        return _dt.datetime.strptime(date_str.strip(), "%b %d, %Y").date()
    except ValueError:
        # Try full month name
        try:
            return _dt.datetime.strptime(date_str.strip(), "%B %d, %Y").date()
        except ValueError:
            return None


###############################################################################
# Lake Shore Funeral Home scraper
###############################################################################


def scrape_lakeshore() -> Iterable[ObituaryRecord]:
    """Scrape the most recent obituaries from Lake Shore Funeral Home.

    This function uses the logic from ``scrape_obituaries.py`` to fetch page 1
    of the obituary listings and extract the name and date range for each entry.
    It then splits the date range into birth and death dates.
    """
    url = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0"
        ),
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ob_records: List[ObituaryRecord] = []
    # Find anchor tags linking to individual obituaries with obId query parameter
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "/obituaries/" not in href or "obId=" not in href:
            continue
        name = a.get_text(strip=True)
        full_url = href if href.startswith("http") else f"https://www.lakeshorefuneralhome.com{href}"
        # Attempt to find the date range in the nearby <p> tag
        date_range = ""
        parent = a.parent
        if parent:
            for p in parent.find_all_next("p", limit=3):
                text = p.get_text(strip=True)
                if "-" in text or "–" in text:
                    date_range = text
                    break
        # Split the date range into birth and death dates
        birth_date: Optional[_dt.date] = None
        death_date: Optional[_dt.date] = None
        if date_range:
            # Normalize dash
            dash = "–" if "–" in date_range else "-"
            parts = [s.strip() for s in date_range.split(dash)]
            if len(parts) == 2:
                birth_date = parse_date(parts[0])
                death_date = parse_date(parts[1])
        ob_records.append(
            ObituaryRecord(
                name=name,
                birth_date=birth_date,
                death_date=death_date,
                url=full_url,
                source="lakeshorefuneralhome.com",
            )
        )
    return ob_records


###############################################################################
# Robertson Funeral & Cremation scraper
###############################################################################


def scrape_robertson() -> Iterable[ObituaryRecord]:
    """Scrape obituaries from Robertson Funeral & Cremation in Marlin, TX.

    The listings page is statically rendered and contains a series of “View”
    links to individual obituary pages.  The individual obituary pages include
    the name and a date line such as “December 5, 1962 ~ July 17, 2025 (age 62)”.
    """
    base_listing = "https://www.robertsonfh.com/listings"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0"
        ),
    }
    resp = requests.get(base_listing, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    records: List[ObituaryRecord] = []

    # Find all 'View' links; these lead to individual obituaries
    for view_link in soup.find_all("a", string=lambda s: s and s.strip().lower() == "view"):
        ob_url = view_link.get("href")
        if not ob_url:
            continue
        full_url = ob_url if ob_url.startswith("http") else f"https://www.robertsonfh.com{ob_url}"
        try:
            ob_resp = requests.get(full_url, headers=headers, timeout=30)
            ob_resp.raise_for_status()
        except Exception:
            continue
        ob_soup = BeautifulSoup(ob_resp.text, "html.parser")
        # Extract name – typically in an <h1> tag
        name_tag = ob_soup.find("h1")
        name = name_tag.get_text(strip=True) if name_tag else ""
        # Extract the line containing dates: e.g. "December 5, 1962 ~ July 17, 2025 (age 62)"
        date_line: Optional[str] = None
        pattern = re.compile(r"\d{4}")  # simple heuristic: line with a 4‑digit year
        for tag in ob_soup.find_all(["h2", "h3", "p"]):
            text = tag.get_text(" ", strip=True)
            if "~" in text and pattern.search(text):
                date_line = text
                break
        birth_date = death_date = None
        if date_line and "~" in date_line:
            parts = [p.strip() for p in date_line.split("~", 1)]
            # Remove age component if present (e.g. "(age 62)")
            def clean(part: str) -> str:
                return re.sub(r"\(.*?\)", "", part).strip()
            if len(parts) == 2:
                birth_date = parse_date(clean(parts[0]))
                death_date = parse_date(clean(parts[1]))
        records.append(
            ObituaryRecord(
                name=name or "", birth_date=birth_date, death_date=death_date, url=full_url, source="robertsonfh.com"
            )
        )
    return records


###############################################################################
# Placeholder scrapers for other funeral homes
###############################################################################


def scrape_placeholder(domain: str) -> Iterable[ObituaryRecord]:
    """Placeholder scraper for funeral homes not yet implemented.

    This function returns an empty list and serves as a template for adding
    additional sites.  To implement a new scraper:

    1. Determine the URL of the funeral home’s obituary listing page.
    2. Fetch the page content using requests (or Selenium if necessary).
    3. Parse out the obituary entries and extract the name, birth and death
       dates, and obituary URL.
    4. Yield ``ObituaryRecord`` instances for each entry.
    """
    # TODO: implement scraping logic for `domain` funeral home
    return []


###############################################################################
# Main aggregation logic
###############################################################################


def aggregate_obituaries() -> List[ObituaryRecord]:
    """Collect obituary records from all configured funeral home scrapers and sort.

    Returns a list of ``ObituaryRecord`` objects sorted by death date (most
    recent first).  Unknown death dates sort to the bottom of the list.
    """
    all_records: List[ObituaryRecord] = []
    scrapers = [scrape_lakeshore, scrape_robertson]
    # Add placeholders for other domains if needed
    # scrapers.append(lambda: scrape_placeholder('aderholdfuneralhome.com'))
    for scraper in scrapers:
        try:
            all_records.extend(scraper())
        except Exception as exc:
            # Log and continue; one failing site should not stop others
            print(f"Warning: failed to scrape using {scraper.__name__}: {exc}")
            continue
    # Sort records by death date descending
    return sorted(all_records, key=lambda r: r.date_key(), reverse=True)


def main():
    records = aggregate_obituaries()
    print(f"Collected {len(records)} obituary records.")
    for rec in records:
        bdate = rec.birth_date.strftime("%b %d, %Y") if rec.birth_date else "Unknown"
        ddate = rec.death_date.strftime("%b %d, %Y") if rec.death_date else "Unknown"
        print(f"{rec.name} — {bdate} to {ddate} — {rec.url} ({rec.source})")


if __name__ == "__main__":
    main()