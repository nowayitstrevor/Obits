from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from time import perf_counter
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None

REQUEST_TIMEOUT_SECONDS = 30
MAX_OBITUARIES_PER_SOURCE = 40
DEFAULT_LOOKBACK_DAYS = 0
DEFAULT_STOP_ON_SEEN = True
DEFAULT_SEEN_STOP_STREAK = 1
CONFIG_PATH = Path(__file__).resolve().parent / "funeral_homes_config.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "obituaries_selected_pages.json"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

DEFAULT_SKIP_PATTERNS = {
    "javascript:",
    "mailto:",
    "tel:",
    "#",
    "/send-flowers",
    "/plant-tree",
    "/guestbook",
    "/guest-book",
    "/directions",
    "/share",
    "/flowers",
}

DEFAULT_OBITUARY_INDICATORS = (
    "/obituary/",
    "/obituaries/",
    "/obit/",
    "/memorial/",
    "/tribute/",
)

DATE_PATTERNS = (
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
    r"\b\d{4}-\d{1,2}-\d{1,2}\b",
)

NOISY_PAGE_TEXT_MARKERS = (
    "this site is protected by recaptcha",
    "please ensure javascript is enabled",
    "enter your phone number above to have directions sent via text",
)

NON_OBITUARY_NAME_MARKERS = (
    "obituary listings",
    "obituary resources",
    "obituary writer",
)

SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)
CLOUD_SCRAPER = (
    cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    if cloudscraper
    else None
)


def create_selenium_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
    except Exception:
        return None

    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    try:
        service = FirefoxService(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=options)
    except Exception:
        return None


def fetch_page_html_with_selenium(driver, url: str, wait_seconds: float = 8.0) -> str | None:
    if driver is None:
        return None
    try:
        from time import sleep

        driver.get(url)
        sleep(wait_seconds)
        return driver.page_source
    except Exception:
        return None


@dataclass
class ObituaryRecord:
    id: str
    sourceKey: str
    sourceName: str
    listingUrl: str
    obituaryUrl: str
    name: str | None = None
    birthDate: str | None = None
    deathDate: str | None = None
    age: int | None = None
    summary: str | None = None
    photoUrl: str | None = None
    scrapedAt: str | None = None


@dataclass
class SourceScrapeResult:
    source: str
    sourceKey: str
    status: str
    listingUrl: str
    pagesDiscovered: int
    obituariesScraped: int
    durationMs: int
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_whitespace(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value).strip(" \t\r\n,;:-")
    return normalized or None


def parse_date_string(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = normalize_whitespace(value)
    if not candidate:
        return None

    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def date_is_reasonable(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.year < 1850:
        return False
    if value > datetime.now() + timedelta(days=500):
        return False
    return True


def collect_date_strings(text: str) -> list[str]:
    found: list[str] = []
    for pattern in DATE_PATTERNS:
        for match in re.findall(pattern, text, re.I):
            normalized = normalize_whitespace(str(match))
            if not normalized:
                continue
            parsed = parse_date_string(normalized)
            if not date_is_reasonable(parsed):
                continue
            if normalized not in found:
                found.append(normalized)
    return found


def infer_birth_death_dates(page_text: str, name_text: str | None = None) -> tuple[str | None, str | None]:
    text = page_text or ""
    name_blob = name_text or ""

    explicit_birth = None
    explicit_birth_match = re.search(
        r"(?:born\s+(?:on\s+)?)((?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    if explicit_birth_match:
        explicit_birth = normalize_whitespace(explicit_birth_match.group(1))

    explicit_death = None
    explicit_death_match = re.search(
        r"(?:passed\s+away\s+on|died\s+on|entered\s+eternal\s+rest\s+on|went\s+home\s+to\s+.*?\s+on|departed\s+this\s+world\s+on)\s*"
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    if explicit_death_match:
        explicit_death = normalize_whitespace(explicit_death_match.group(1))

    title_death = None
    title_death_match = re.search(
        r"obituary\s+((?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})",
        name_blob,
        re.I,
    )
    if title_death_match:
        title_death = normalize_whitespace(title_death_match.group(1))

    range_match = re.search(
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})\s*[—–-]\s*"
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    if range_match:
        first = normalize_whitespace(range_match.group(1))
        second = normalize_whitespace(range_match.group(2))
        first_dt = parse_date_string(first)
        second_dt = parse_date_string(second)
        if date_is_reasonable(first_dt) and date_is_reasonable(second_dt):
            if first_dt <= second_dt:
                return first, second
            return second, first

    death = explicit_death or title_death
    birth = explicit_birth

    dates = collect_date_strings(text)
    parsed_dates = [(value, parse_date_string(value)) for value in dates]
    parsed_dates = [(value, parsed) for value, parsed in parsed_dates if date_is_reasonable(parsed)]

    if death and not birth:
        death_dt = parse_date_string(death)
        older = [value for value, parsed in parsed_dates if death_dt and parsed and parsed < death_dt]
        if older:
            birth = older[0]

    if not death and parsed_dates:
        death = max(parsed_dates, key=lambda item: item[1])[0]

    if not birth and parsed_dates:
        earliest = min(parsed_dates, key=lambda item: item[1])[0]
        if earliest != death:
            birth = earliest

    birth_dt = parse_date_string(birth)
    death_dt = parse_date_string(death)
    if birth_dt and death_dt and death_dt < birth_dt:
        birth, death = death, birth

    return birth, death


def extract_first_text(soup: BeautifulSoup, selectors_csv: str | None) -> str | None:
    if not selectors_csv:
        return None

    selectors = [token.strip() for token in selectors_csv.split(",") if token.strip()]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = normalize_whitespace(node.get_text(" ", strip=True))
        if text:
            return text

    return None


def fetch_with_fallback(url: str, timeout: int = REQUEST_TIMEOUT_SECONDS, prefer_cloudscraper: bool = False) -> requests.Response:
    if prefer_cloudscraper and CLOUD_SCRAPER is not None:
        response = CLOUD_SCRAPER.get(url, timeout=timeout)
        if response.status_code < 500:
            return response

    response = SESSION.get(url, timeout=timeout)
    if response.status_code == 403 and CLOUD_SCRAPER is not None:
        cloud_response = CLOUD_SCRAPER.get(url, timeout=timeout)
        if cloud_response.status_code < 500:
            return cloud_response

    return response


def normalize_obituary_url(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate.lower().rstrip("/")

    normalized_path = parsed.path or "/"
    normalized_path = re.sub(r"/+", "/", normalized_path)
    normalized_path = normalized_path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{normalized_path}"


def load_seen_obituary_urls_by_source(output_path: Path) -> dict[str, set[str]]:
    if not output_path.exists():
        return {}

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    raw_obituaries = payload.get("obituaries")
    if not isinstance(raw_obituaries, list):
        return {}

    seen_by_source: dict[str, set[str]] = {}
    for item in raw_obituaries:
        if not isinstance(item, dict):
            continue

        source_key = str(item.get("sourceKey") or "").strip()
        obituary_url = normalize_obituary_url(str(item.get("obituaryUrl") or "").strip())
        if not source_key or not obituary_url:
            continue

        seen_by_source.setdefault(source_key, set()).add(obituary_url)

    return seen_by_source


def load_previous_records_by_source(output_path: Path) -> dict[str, list[ObituaryRecord]]:
    if not output_path.exists():
        return {}

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    raw_obituaries = payload.get("obituaries")
    if not isinstance(raw_obituaries, list):
        return {}

    records_by_source: dict[str, list[ObituaryRecord]] = {}
    for item in raw_obituaries:
        if not isinstance(item, dict):
            continue

        source_key = str(item.get("sourceKey") or "").strip()
        obituary_id = str(item.get("id") or "").strip()
        obituary_url = str(item.get("obituaryUrl") or "").strip()
        if not source_key or not obituary_id or not obituary_url:
            continue

        age_value = item.get("age")
        try:
            parsed_age = int(age_value) if age_value is not None else None
        except (TypeError, ValueError):
            parsed_age = None

        record = ObituaryRecord(
            id=obituary_id,
            sourceKey=source_key,
            sourceName=str(item.get("sourceName") or source_key),
            listingUrl=str(item.get("listingUrl") or ""),
            obituaryUrl=obituary_url,
            name=item.get("name"),
            birthDate=item.get("birthDate"),
            deathDate=item.get("deathDate"),
            age=parsed_age,
            summary=item.get("summary"),
            photoUrl=item.get("photoUrl"),
            scrapedAt=item.get("scrapedAt"),
        )
        records_by_source.setdefault(source_key, []).append(record)

    return records_by_source


def merge_records_prefer_new(new_records: list[ObituaryRecord], previous_records: list[ObituaryRecord]) -> list[ObituaryRecord]:
    merged_by_url: dict[str, ObituaryRecord] = {}

    for record in previous_records:
        merge_key = normalize_obituary_url(record.obituaryUrl) or record.id.lower()
        if merge_key and merge_key not in merged_by_url:
            merged_by_url[merge_key] = record

    for record in new_records:
        merge_key = normalize_obituary_url(record.obituaryUrl) or record.id.lower()
        if not merge_key:
            continue
        merged_by_url[merge_key] = record

    deduped_by_id: list[ObituaryRecord] = []
    seen_ids: set[str] = set()
    for record in merged_by_url.values():
        if record.id in seen_ids:
            continue
        seen_ids.add(record.id)
        deduped_by_id.append(record)

    return deduped_by_id


def should_skip_link(url: str, skip_patterns: set[str]) -> bool:
    lowered = url.lower().strip()
    if not lowered:
        return True

    if lowered.startswith("javascript:") or lowered.startswith("mailto:") or lowered.startswith("tel:"):
        return True

    parsed_path = urlparse(lowered).path.rstrip("/")
    path_only_patterns = {"/obituaries", "/obituary-search", "/search", "/listings"}

    for pattern in skip_patterns:
        if not pattern:
            continue

        token = pattern.lower().strip()
        if token in path_only_patterns:
            if parsed_path == token.rstrip("/"):
                return True
            continue

        if token in lowered:
            return True

    return False


def is_obituary_url(url: str, indicators: Iterable[str]) -> bool:
    lowered = url.lower()
    return any(token.lower() in lowered for token in indicators)


def extract_sitemap_urls_from_robots(base_url: str) -> list[str]:
    sitemap_urls: list[str] = []
    seen: set[str] = set()

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return sitemap_urls

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = fetch_with_fallback(robots_url, prefer_cloudscraper=True)
        if response.status_code >= 400:
            return sitemap_urls
    except Exception:
        return sitemap_urls

    for line in response.text.splitlines():
        line = line.strip()
        if not line.lower().startswith("sitemap:"):
            continue
        candidate = line.split(":", 1)[1].strip()
        if not candidate:
            continue
        absolute = urljoin(robots_url, candidate)
        if absolute in seen:
            continue
        seen.add(absolute)
        sitemap_urls.append(absolute)

    return sitemap_urls


def extract_urls_from_sitemap(sitemap_url: str) -> tuple[list[str], list[str]]:
    try:
        response = fetch_with_fallback(sitemap_url, prefer_cloudscraper=True)
        response.raise_for_status()
    except Exception:
        return [], []

    text = response.text
    url_entries = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text, re.I)
    sitemap_entries: list[str] = []
    page_entries: list[str] = []

    for entry in url_entries:
        absolute = urljoin(sitemap_url, entry.strip())
        lowered = absolute.lower()
        if lowered.endswith(".xml") or "sitemap" in lowered:
            sitemap_entries.append(absolute)
        else:
            page_entries.append(absolute)

    return sitemap_entries, page_entries


def discover_obituary_urls_from_sitemaps(listing_url: str, skip_patterns: set[str], indicators: Iterable[str], max_urls: int) -> list[str]:
    seed_sitemaps = extract_sitemap_urls_from_robots(listing_url)

    parsed_listing = urlparse(listing_url)
    if parsed_listing.scheme and parsed_listing.netloc:
        root = f"{parsed_listing.scheme}://{parsed_listing.netloc}"
        for extra in (
            "/obituary-sitemap.xml",
            "/sitemap.xml",
        ):
            candidate = root + extra
            if candidate not in seed_sitemaps:
                seed_sitemaps.append(candidate)

    discovered: list[str] = []
    seen_urls: set[str] = set()
    queue: list[str] = seed_sitemaps[:]
    seen_sitemaps: set[str] = set()

    while queue and len(discovered) < max_urls:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        nested_sitemaps, page_urls = extract_urls_from_sitemap(sitemap_url)
        for nested in nested_sitemaps:
            if nested not in seen_sitemaps:
                queue.append(nested)

        for page_url in page_urls:
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            if should_skip_link(page_url, skip_patterns):
                continue
            if not is_obituary_url(page_url, indicators):
                continue
            discovered.append(page_url)
            if len(discovered) >= max_urls:
                break

    return discovered


def extract_candidate_links(listing_soup: BeautifulSoup, listing_url: str, selectors: dict, skip_patterns: set[str], indicators: Iterable[str]) -> list[str]:
    links: list[str] = []
    unique: set[str] = set()

    containers = []
    obituary_list_selector = selectors.get("obituary_list")
    if obituary_list_selector:
        try:
            containers = listing_soup.select(obituary_list_selector)
        except Exception:
            containers = []

    if containers:
        obituary_link_selector = selectors.get("obituary_link", "a[href]")
        for container in containers:
            try:
                anchors = container.select(obituary_link_selector)
            except Exception:
                anchors = container.select("a[href]")

            for anchor in anchors:
                href = (anchor.get("href") or "").strip()
                if not href:
                    continue
                absolute = urljoin(listing_url, href)
                if should_skip_link(absolute, skip_patterns):
                    continue
                if not is_obituary_url(absolute, indicators):
                    continue
                if absolute in unique:
                    continue
                unique.add(absolute)
                links.append(absolute)

    if links:
        return links

    for anchor in listing_soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(listing_url, href)
        if should_skip_link(absolute, skip_patterns):
            continue
        if not is_obituary_url(absolute, indicators):
            continue
        if absolute in unique:
            continue
        unique.add(absolute)
        links.append(absolute)

    return links


def extract_dates(page_text: str) -> tuple[str | None, str | None]:
    return infer_birth_death_dates(page_text)


def clean_extracted_name(value: str | None, source_name: str | None = None) -> str | None:
    name = normalize_whitespace(value)
    if not name:
        return None

    date_fragment = (
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
        r"|\d{4}-\d{1,2}-\d{1,2}"
    )

    name = re.sub(r"^(?:obituary\s+for|obituary\s+of|in\s+loving\s+memory\s+of)\s+", "", name, flags=re.I)
    name = re.sub(r"\s*\|\s*\d{4}\s*-\s*\d{4}\s*\|\s*obituary\b.*$", "", name, flags=re.I)
    name = re.sub(r"^obituary\s*\|\s*", "", name, flags=re.I)
    name = re.sub(r"\s*\|\s*obituary\b.*$", "", name, flags=re.I)
    name = re.sub(rf"\s+obituary\s+{date_fragment}\b.*$", "", name, flags=re.I)
    name = re.sub(
        r"\s*(?:\||[-–—])\s*[^|]*\b(funeral\s+home|funeral\s+services|memorial|mortuary|chapel|cremation|crematorium|cemetery)\b.*$",
        "",
        name,
        flags=re.I,
    )

    normalized_source_name = normalize_whitespace(source_name)
    if normalized_source_name:
        name = re.sub(
            rf"\s*(?:\||[-–—])\s*{re.escape(normalized_source_name)}\s*$",
            "",
            name,
            flags=re.I,
        )

    name = re.sub(r"\s*(?:\||[-–—])\s*obituary\s*$", "", name, flags=re.I)
    name = normalize_whitespace(name)
    return name


def clean_extracted_summary(value: str | None) -> str | None:
    summary = normalize_whitespace(value)
    if not summary:
        return None

    summary = re.sub(
        r"\bshare this obituary\b.*?\bsend sympathy card\b\s*\|?\s*",
        "",
        summary,
        flags=re.I,
    )
    summary = re.sub(r"\bupload photo\b\s*\|?\s*", "", summary, flags=re.I)
    summary = re.sub(r"\bsign guestbook\b\s*\|?\s*", "", summary, flags=re.I)
    summary = re.sub(r"\bview guestbook entries\b\s*\|?\s*", "", summary, flags=re.I)
    summary = normalize_whitespace(summary)
    return summary[:700] if summary else None


def extract_summary(soup: BeautifulSoup, selectors: dict) -> str | None:
    configured = extract_first_text(soup, selectors.get("content_selector"))
    if configured and len(configured) >= 80:
        return clean_extracted_summary(configured)

    paragraphs = [normalize_whitespace(p.get_text(" ", strip=True)) for p in soup.select("p")]
    for paragraph in paragraphs:
        if not paragraph:
            continue
        if 80 <= len(paragraph) <= 1200:
            return clean_extracted_summary(paragraph)

    body = normalize_whitespace(soup.get_text(" ", strip=True))
    if body and len(body) >= 120:
        return clean_extracted_summary(body)

    return None


def extract_photo_url(soup: BeautifulSoup, page_url: str, selectors: dict) -> str | None:
    configured_selector = selectors.get("photo_selector")
    if configured_selector:
        node = soup.select_one(configured_selector)
        if node and node.get("src"):
            return urljoin(page_url, node.get("src"))

    meta_image = soup.select_one("meta[property='og:image'], meta[name='twitter:image'], meta[itemprop='image']")
    if meta_image and meta_image.get("content"):
        return urljoin(page_url, meta_image.get("content"))

    ld_json_nodes = soup.select("script[type='application/ld+json']")
    for node in ld_json_nodes:
        text = node.string or node.get_text("", strip=True)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            image_value = item.get("image")
            if isinstance(image_value, str) and image_value.strip():
                return urljoin(page_url, image_value.strip())
            if isinstance(image_value, list):
                for image_entry in image_value:
                    if isinstance(image_entry, str) and image_entry.strip():
                        return urljoin(page_url, image_entry.strip())

    for selector in [
        ".obit-photo img",
        ".memorial-photo img",
        ".tukios--obituary-listing-image img",
        ".tukios--obituary-listing-item img",
        "img[src*='obit']",
        "img[src*='obituary']",
        "img[src*='tribute']",
    ]:
        node = soup.select_one(selector)
        if not node or not node.get("src"):
            continue
        return urljoin(page_url, node.get("src"))

    for img in soup.select("img[src]"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        lowered = src.lower()
        if any(marker in lowered for marker in ("logo", "icon", "sprite", "placeholder", "avatar-default")):
            continue
        if lowered.startswith("data:"):
            continue
        return urljoin(page_url, src)

    return None


def extract_listing_photo_map(listing_soup: BeautifulSoup, listing_url: str, skip_patterns: set[str], indicators: Iterable[str]) -> dict[str, str]:
    photo_map: dict[str, str] = {}

    for anchor in listing_soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        obituary_url = urljoin(listing_url, href)
        if should_skip_link(obituary_url, skip_patterns):
            continue
        if not is_obituary_url(obituary_url, indicators):
            continue

        image = anchor.select_one("img")
        if image is None and anchor.parent is not None:
            image = anchor.parent.select_one("img")
        if image is None:
            continue

        src = (image.get("src") or "").strip()
        if not src:
            continue

        absolute = urljoin(listing_url, src)
        if absolute:
            photo_map[obituary_url] = absolute

    return photo_map


def is_non_obituary_record(record: ObituaryRecord) -> bool:
    name = (record.name or "").lower()
    summary = (record.summary or "").lower()
    url = (record.obituaryUrl or "").lower()

    if any(marker in name for marker in NON_OBITUARY_NAME_MARKERS):
        return True

    if any(token in url for token in ("/send-flowers", "/obituary-resources", "/obituary-writer", "/sympathy", "/obituary-listings")):
        return True

    return False


def generate_obituary_id(url: str) -> str:
    parsed = urlparse(url)
    candidates = [segment for segment in parsed.path.split("/") if segment]
    if candidates:
        tail = re.sub(r"\.(html?|php|asp|jsp)$", "", candidates[-1], flags=re.I)
        tail = re.sub(r"[^a-zA-Z0-9_-]", "", tail)
        if tail:
            return tail[:120]
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:16]


def build_obituary_record_from_soup(
    soup: BeautifulSoup,
    obituary_url: str,
    listing_url: str,
    source_key: str,
    source_name: str,
    selectors: dict,
) -> ObituaryRecord | None:
    page_text = normalize_whitespace(soup.get_text(" ", strip=True)) or ""

    name = extract_first_text(soup, selectors.get("name_selector"))
    if not name:
        name = normalize_whitespace((soup.select_one("h1") or soup.select_one("title") or {}).get_text(" ", strip=True) if (soup.select_one("h1") or soup.select_one("title")) else None)
    name = clean_extracted_name(name, source_name=source_name)

    birth_date = extract_first_text(soup, selectors.get("birth_date"))
    death_date = extract_first_text(soup, selectors.get("death_date"))

    if not birth_date:
        birth_date = extract_first_text(soup, ".dob, [itemprop='birthDate'], time[itemprop='birthDate']")
    if not death_date:
        death_date = extract_first_text(soup, ".dod, [itemprop='deathDate'], time[itemprop='deathDate']")

    if not birth_date or not death_date:
        inferred_birth, inferred_death = infer_birth_death_dates(page_text, name_text=name)
        birth_date = birth_date or inferred_birth
        death_date = death_date or inferred_death

    age_value: int | None = None
    age_text = extract_first_text(soup, selectors.get("age_selector"))
    if age_text:
        age_match = re.search(r"\b(\d{1,3})\b", age_text)
        if age_match:
            age_value = int(age_match.group(1))
    if age_value is None:
        global_age_match = re.search(r"\bage\s*(\d{1,3})\b", page_text, re.I)
        if global_age_match:
            age_value = int(global_age_match.group(1))

    return ObituaryRecord(
        id=generate_obituary_id(obituary_url),
        sourceKey=source_key,
        sourceName=source_name,
        listingUrl=listing_url,
        obituaryUrl=obituary_url,
        name=name,
        birthDate=birth_date,
        deathDate=death_date,
        age=age_value,
        summary=extract_summary(soup, selectors),
        photoUrl=extract_photo_url(soup, obituary_url, selectors),
        scrapedAt=now_iso(),
    )


def scrape_obituary_page(
    obituary_url: str,
    listing_url: str,
    source_key: str,
    source_name: str,
    selectors: dict,
    selenium_driver=None,
    allow_selenium_fallback: bool = False,
) -> ObituaryRecord | None:
    try:
        page_response = fetch_with_fallback(obituary_url, prefer_cloudscraper=True)
        if page_response.status_code < 400:
            soup = BeautifulSoup(page_response.text, "html.parser")
            record = build_obituary_record_from_soup(soup, obituary_url, listing_url, source_key, source_name, selectors)
            if record and (record.name or record.summary):
                return record
    except Exception:
        pass

    if allow_selenium_fallback and selenium_driver is not None:
        html = fetch_page_html_with_selenium(selenium_driver, obituary_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            record = build_obituary_record_from_soup(soup, obituary_url, listing_url, source_key, source_name, selectors)
            if record and (record.name or record.summary):
                return record

    return None


def scrape_source(
    source_key: str,
    config: dict,
    max_obituaries: int,
    known_obituary_urls: set[str] | None = None,
    stop_on_seen: bool = DEFAULT_STOP_ON_SEEN,
    seen_stop_streak: int = DEFAULT_SEEN_STOP_STREAK,
) -> tuple[list[ObituaryRecord], SourceScrapeResult]:
    source_name = str(config.get("name") or source_key)
    listing_url = str(config.get("url") or "").strip()
    selectors = config.get("custom_selectors") or {}

    started = perf_counter()

    if not listing_url:
        duration = int((perf_counter() - started) * 1000)
        return [], SourceScrapeResult(
            source=source_name,
            sourceKey=source_key,
            status="error",
            listingUrl=listing_url,
            pagesDiscovered=0,
            obituariesScraped=0,
            durationMs=duration,
            error="Missing url in configuration",
        )

    selenium_driver = None
    requires_javascript = bool(config.get("requires_javascript", False))
    if requires_javascript:
        selenium_driver = create_selenium_driver()

    try:
        listing_response = fetch_with_fallback(listing_url, prefer_cloudscraper=True)
        listing_response.raise_for_status()

        listing_soup = BeautifulSoup(listing_response.text, "html.parser")
        custom_skips = {str(item).lower() for item in config.get("skip_patterns", []) if str(item).strip()}
        skip_patterns = DEFAULT_SKIP_PATTERNS | custom_skips

        url_patterns = config.get("url_patterns") or {}
        indicators = url_patterns.get("obituary_indicators") or DEFAULT_OBITUARY_INDICATORS

        obituary_urls = extract_candidate_links(listing_soup, listing_url, selectors, skip_patterns, indicators)
        listing_photo_map = extract_listing_photo_map(listing_soup, listing_url, skip_patterns, indicators)
        if not obituary_urls and selenium_driver is not None:
            selenium_html = fetch_page_html_with_selenium(selenium_driver, listing_url)
            if selenium_html:
                selenium_soup = BeautifulSoup(selenium_html, "html.parser")
                obituary_urls = extract_candidate_links(selenium_soup, listing_url, selectors, skip_patterns, indicators)
                listing_photo_map.update(extract_listing_photo_map(selenium_soup, listing_url, skip_patterns, indicators))

        if not obituary_urls:
            obituary_urls = discover_obituary_urls_from_sitemaps(
                listing_url=listing_url,
                skip_patterns=skip_patterns,
                indicators=indicators,
                max_urls=max_obituaries,
            )

        obituary_urls = obituary_urls[:max_obituaries]

        known_urls = known_obituary_urls or set()
        required_seen_streak = max(1, int(seen_stop_streak))
        urls_to_scrape: list[str] = []
        seen_streak = 0

        for obituary_url in obituary_urls:
            normalized_obituary_url = normalize_obituary_url(obituary_url)
            if stop_on_seen and known_urls and normalized_obituary_url in known_urls:
                seen_streak += 1
                if seen_streak >= required_seen_streak:
                    break
                continue

            seen_streak = 0
            urls_to_scrape.append(obituary_url)

        records: list[ObituaryRecord] = []
        seen_ids: set[str] = set()
        for obituary_url in urls_to_scrape:
            record = scrape_obituary_page(
                obituary_url,
                listing_url,
                source_key,
                source_name,
                selectors,
                selenium_driver=selenium_driver,
                allow_selenium_fallback=selenium_driver is not None,
            )
            if not record:
                continue
            if not record.photoUrl and obituary_url in listing_photo_map:
                record.photoUrl = listing_photo_map[obituary_url]
            if is_non_obituary_record(record):
                continue
            if record.id in seen_ids:
                continue
            seen_ids.add(record.id)
            records.append(record)

        duration = int((perf_counter() - started) * 1000)
        status = "ok" if records else "no-data"
        return records, SourceScrapeResult(
            source=source_name,
            sourceKey=source_key,
            status=status,
            listingUrl=listing_url,
            pagesDiscovered=len(urls_to_scrape),
            obituariesScraped=len(records),
            durationMs=duration,
            error=None,
        )

    except Exception as error:
        duration = int((perf_counter() - started) * 1000)
        return [], SourceScrapeResult(
            source=source_name,
            sourceKey=source_key,
            status="error",
            listingUrl=listing_url,
            pagesDiscovered=0,
            obituariesScraped=0,
            durationMs=duration,
            error=str(error),
        )
    finally:
        if selenium_driver is not None:
            try:
                selenium_driver.quit()
            except Exception:
                pass


def load_selected_sources(include_inactive: bool, source_keys: set[str] | None) -> dict[str, dict]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    all_sources = payload.get("funeral_homes", {})

    selected: dict[str, dict] = {}
    for key, config in all_sources.items():
        if source_keys and key not in source_keys:
            continue
        if not include_inactive and not bool(config.get("active", False)):
            continue
        selected[key] = config

    return dict(sorted(selected.items(), key=lambda item: int(item[1].get("priority", 999))))


def filter_records_to_lookback(records: list[ObituaryRecord], lookback_days: int) -> list[ObituaryRecord]:
    if lookback_days <= 0:
        return records

    cutoff = datetime.now() - timedelta(days=lookback_days)
    filtered: list[ObituaryRecord] = []
    for record in records:
        death_dt = parse_date_string(record.deathDate)
        if death_dt is None:
            continue
        if death_dt >= cutoff:
            filtered.append(record)
    return filtered


def collect_all_obituaries(
    include_inactive: bool,
    source_keys: set[str] | None,
    max_obituaries: int,
    lookback_days: int,
    stop_on_seen: bool,
    seen_stop_streak: int,
) -> tuple[list[ObituaryRecord], list[SourceScrapeResult]]:
    records: list[ObituaryRecord] = []
    report: list[SourceScrapeResult] = []

    sources = load_selected_sources(include_inactive=include_inactive, source_keys=source_keys)
    if not sources:
        raise ValueError("No sources selected. Check --sources or funeral_homes_config.json active flags.")

    previous_records_by_source = load_previous_records_by_source(OUTPUT_PATH) if stop_on_seen else {}
    seen_urls_by_source = load_seen_obituary_urls_by_source(OUTPUT_PATH) if stop_on_seen else {}

    for source_key, config in sources.items():
        previous_source_records = previous_records_by_source.get(source_key, [])
        known_obituary_urls = seen_urls_by_source.get(source_key, set())
        source_records, source_result = scrape_source(
            source_key,
            config,
            max_obituaries=max_obituaries,
            known_obituary_urls=known_obituary_urls,
            stop_on_seen=stop_on_seen,
            seen_stop_streak=seen_stop_streak,
        )

        if stop_on_seen and previous_source_records:
            source_records = merge_records_prefer_new(source_records, previous_source_records)

        source_records = filter_records_to_lookback(source_records, lookback_days=lookback_days)
        source_result.obituariesScraped = len(source_records)
        if source_result.status == "no-data" and source_records:
            source_result.status = "ok"
        if source_result.status == "ok" and not source_records:
            source_result.status = "no-data"
        records.extend(source_records)
        report.append(source_result)
        status_marker = "ok" if source_result.status == "ok" else source_result.status
        print(f"[{source_result.source}] {status_marker}: {source_result.obituariesScraped} pages scraped")

    records.sort(key=lambda item: (item.sourceName.lower(), item.name or ""))
    return records, report


def write_output(records: list[ObituaryRecord], source_results: list[SourceScrapeResult]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": now_iso(),
        "obituaries": [asdict(item) for item in records],
        "scrapeReport": {
            "sources": [asdict(result) for result in source_results],
            "successfulSources": sum(1 for item in source_results if item.status in {"ok", "no-data"}),
            "failedSources": sum(1 for item in source_results if item.status == "error"),
            "totalObituaries": len(records),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape obituaries from selected funeral home pages.")
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated funeral home keys from funeral_homes_config.json (example: foss,robertson,slctx)",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include sources marked active=false in funeral_homes_config.json",
    )
    parser.add_argument(
        "--max-obituaries-per-source",
        type=int,
        default=MAX_OBITUARIES_PER_SOURCE,
        help=f"Maximum obituary pages to scrape per source (default: {MAX_OBITUARIES_PER_SOURCE})",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Keep only obituaries with death dates within the last N days (default: {DEFAULT_LOOKBACK_DAYS} = keep all)",
    )
    parser.add_argument(
        "--stop-on-seen",
        dest="stop_on_seen",
        action="store_true",
        default=DEFAULT_STOP_ON_SEEN,
        help="Stop scraping older obituary pages for a source once already-scraped obituary URLs are reached.",
    )
    parser.add_argument(
        "--no-stop-on-seen",
        dest="stop_on_seen",
        action="store_false",
        help="Disable stop-on-seen behavior and scrape up to --max-obituaries-per-source each run.",
    )
    parser.add_argument(
        "--seen-stop-streak",
        type=int,
        default=DEFAULT_SEEN_STOP_STREAK,
        help=f"Consecutive already-seen obituary URLs required before stopping a source (default: {DEFAULT_SEEN_STOP_STREAK}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_keys = {token.strip() for token in (args.sources or "").split(",") if token.strip()} or None

    records, source_results = collect_all_obituaries(
        include_inactive=args.include_inactive,
        source_keys=source_keys,
        max_obituaries=max(1, int(args.max_obituaries_per_source)),
        lookback_days=max(0, int(args.lookback_days)),
        stop_on_seen=bool(args.stop_on_seen),
        seen_stop_streak=max(1, int(args.seen_stop_streak)),
    )
    write_output(records, source_results)

    total = len(records)
    print(f"Saved {total} obituary pages to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
