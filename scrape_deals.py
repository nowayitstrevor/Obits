from __future__ import annotations

import json
import re
import html
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None

VALUE_DEAL_THRESHOLD_PER_LB = 6.50
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "green-coffee-deals.json"
REQUEST_TIMEOUT_SECONDS = 25
NOISY_TAGS = {
    "green",
    "green coffee",
    "green-coffee",
    "green coffee beans",
    "coffee",
    "beans",
    "single-origin",
    "single origin",
    "sale",
    "new",
    "new arrivals",
    "essentials",
    "active",
    "archive",
    "unroasted",
    "sample pack",
}
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)
CLOUD_SCRAPER = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False}) if cloudscraper else None


@dataclass
class GreenCoffeeDeal:
    source: str
    name: str
    pricePerLb: float | None = None
    productUrl: str | None = None
    origin: str | None = None
    process: str | None = None
    score: float | None = None
    notes: str | None = None
    size: str | None = None
    priceText: str | None = None
    previousPricePerLb: float | None = None
    dealTag: str | None = None
    isValueDeal: bool = False
    collectedAt: str | None = None


@dataclass
class SourceScrapeResult:
    source: str
    status: str
    dealsCollected: int
    durationMs: int
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_price_per_lb(price: float) -> float:
    return round(float(price), 2)


def parse_weight_lbs(size_text: str | None) -> float | None:
    if not size_text:
        return None

    normalized = size_text.strip().lower()
    number_text = ""
    for char in normalized:
        if char.isdigit() or char == ".":
            number_text += char
        elif number_text:
            break

    if not number_text:
        return None

    try:
        value = float(number_text)
    except ValueError:
        return None

    if "kg" in normalized:
        return value * 2.20462
    if "gram" in normalized or " g" in normalized or normalized.endswith("g"):
        return value / 453.592
    if "oz" in normalized:
        return value / 16
    if "lb" in normalized or "pound" in normalized:
        return value

    return None


def infer_origin_from_title(name: str) -> str | None:
    if not name:
        return None
    head = name.split(" ")[0].strip()
    return head or None


def normalize_tag_notes(raw_tags: object | None) -> str | None:
    if not raw_tags:
        return None

    cleaned_tags: list[str] = []
    raw_values: list[str]
    if isinstance(raw_tags, list):
        raw_values = [str(item) for item in raw_tags]
    else:
        raw_values = str(raw_tags).split(",")

    for raw in raw_values:
        candidate = str(raw).strip().strip("[]'")
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in NOISY_TAGS:
            continue
        cleaned_tags.append(candidate)

    unique_tags: list[str] = []
    seen_lower: set[str] = set()
    for tag in cleaned_tags:
        lowered = tag.lower()
        if lowered in seen_lower:
            continue
        seen_lower.add(lowered)
        unique_tags.append(tag)

    return ", ".join(unique_tags) if unique_tags else None


def extract_notes_from_text(text: str | None) -> str | None:
    if not text:
        return None

    normalized = re.sub(r"\s+", " ", text).strip(" \t\r\n,;:-")
    if not normalized:
        return None

    if len(normalized) > 220:
        normalized = normalized[:220].rstrip(" ,;:-")
    return normalized


def extract_tasting_notes_from_html(page_text: str) -> str | None:
    pattern = re.compile(
        r"tasting\s*notes?\s*[:\-]?\s*</?[^>]*>?\s*([^<\n\r]{8,220})",
        re.I,
    )
    match = pattern.search(page_text)
    if match:
        return extract_notes_from_text(match.group(1))

    return None


def extract_hacea_notes_from_product_page(handle: str) -> str | None:
    if not handle:
        return None

    url = f"https://haceacoffee.com/products/{handle}"
    try:
        response = fetch_with_fallback(url)
        if response.status_code >= 400:
            return None
    except Exception:
        return None

    page_text = response.text
    tasting_patterns = [
        r"Tasting\s*Notes\s*:\s*([^\"<]{12,320})",
        r"tasting\s*notes\s*[:\-]\s*([^<\n\r]{12,320})",
    ]

    for pattern in tasting_patterns:
        match = re.search(pattern, page_text, re.I)
        if not match:
            continue
        notes = extract_notes_from_text(html.unescape(match.group(1)))
        if notes:
            return notes

    soup = BeautifulSoup(page_text, "html.parser")
    for node in soup.select("[id*='tasting'], [class*='tasting'], [data-tab*='tasting']"):
        notes = extract_notes_from_text(node.get_text(" ", strip=True))
        if notes and len(notes) >= 20 and "tasting notes" not in notes.lower():
            return notes

    return None


def extract_happy_mug_notes_from_body_html(body_html: str | None) -> str | None:
    if not body_html:
        return None

    text = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
    if not text:
        return None

    explicit_patterns = [
        r"(?:tasting\s*notes?|cup\s*profile|flavor\s*profile|flavour\s*profile)\s*[:\-]?\s*([^\.\n\r]{12,240})",
        r"(?:flavors?\s*of|notes?\s*of|tastes?\s*like)\s*([^\.\n\r]{12,240})",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        notes = extract_notes_from_text(match.group(1))
        if notes:
            return notes

    flavor_keywords = {
        "chocolate",
        "berry",
        "citrus",
        "caramel",
        "peach",
        "apple",
        "floral",
        "honey",
        "spice",
        "nut",
        "grape",
        "cherry",
        "orange",
        "lime",
        "lemon",
        "stone fruit",
    }

    for sentence in re.split(r"(?<=[\.!?])\s+", text):
        cleaned = extract_notes_from_text(sentence)
        if not cleaned or len(cleaned) < 20 or len(cleaned) > 220:
            continue
        lowered = cleaned.lower()
        keyword_hits = sum(1 for keyword in flavor_keywords if keyword in lowered)
        if keyword_hits >= 2:
            return cleaned

    return None


def derive_notes_from_name(name: str, fallback_text: str | None = None) -> str | None:
    source_text = f"{name} {fallback_text or ''}".lower()
    labels: list[str] = []

    keyword_labels = [
        ("washed", "Washed"),
        ("natural", "Natural"),
        ("honey", "Honey Process"),
        ("anaerobic", "Anaerobic"),
        ("swiss water", "Swiss Water Decaf"),
        ("decaf", "Decaf"),
        ("organic", "Organic"),
        ("gesha", "Gesha"),
        ("pacamara", "Pacamara"),
        ("bourbon", "Bourbon"),
        ("caturra", "Caturra"),
    ]

    for keyword, label in keyword_labels:
        if keyword in source_text:
            labels.append(label)

    if not labels:
        return None

    unique_labels: list[str] = []
    seen: set[str] = set()
    for label in labels:
        lowered = label.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_labels.append(label)

    return ", ".join(unique_labels) if unique_labels else None


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


def annotate_deal(deal: GreenCoffeeDeal) -> GreenCoffeeDeal:
    if deal.pricePerLb is not None and Number_isfinite(deal.pricePerLb):
        deal.pricePerLb = normalize_price_per_lb(deal.pricePerLb)
        deal.isValueDeal = deal.pricePerLb <= VALUE_DEAL_THRESHOLD_PER_LB
    else:
        deal.pricePerLb = None
        deal.isValueDeal = False
    deal.collectedAt = now_iso()
    return deal


def Number_isfinite(value: float | None) -> bool:
    if value is None:
        return False
    try:
        return float(value) == float(value) and abs(float(value)) != float("inf")
    except Exception:
        return False


def parse_hacea() -> list[GreenCoffeeDeal]:
    deals: list[GreenCoffeeDeal] = []
    notes_by_handle: dict[str, str | None] = {}
    url = "https://haceacoffee.com/collections/green-coffee/products.json"

    response = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    for product in payload.get("products", []):
        product_tags = product.get("tags", "")
        if isinstance(product_tags, list):
            tags = {str(tag).strip().lower() for tag in product_tags if str(tag).strip()}
        else:
            tags = {tag.strip().lower() for tag in str(product_tags).split(",") if tag.strip()}
        title = str(product.get("title", "")).strip()
        handle = str(product.get("handle") or "").strip()
        if not title:
            continue

        if handle not in notes_by_handle:
            page_notes = extract_hacea_notes_from_product_page(handle) if handle else None
            notes_by_handle[handle] = page_notes or derive_notes_from_name(title) or normalize_tag_notes(product_tags)
        notes = notes_by_handle.get(handle) or derive_notes_from_name(title) or normalize_tag_notes(product_tags)

        for variant in product.get("variants", []):
            price_raw = variant.get("price")
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                continue

            size = variant.get("title") or None
            weight_lbs = parse_weight_lbs(size)
            price_per_lb = (price / weight_lbs) if weight_lbs and weight_lbs > 0 else price
            tag_hint = None
            if "deal" in tags or "sale" in tags:
                tag_hint = "Tagged Deal"

            deal = annotate_deal(
                GreenCoffeeDeal(
                    source="Hacea Coffee",
                    name=title,
                    origin=infer_origin_from_title(title),
                    pricePerLb=price_per_lb,
                    size=size,
                    priceText=str(price_raw) if price_raw is not None else None,
                    productUrl=f"https://haceacoffee.com/products/{handle}" if handle else None,
                    dealTag=tag_hint,
                    notes=notes,
                )
            )
            deals.append(deal)

    return deals


def parse_sweet_marias() -> list[GreenCoffeeDeal]:
    deals: list[GreenCoffeeDeal] = []
    url = "https://www.sweetmarias.com/green-coffee.html"
    response = fetch_with_fallback(url, prefer_cloudscraper=True)
    response.raise_for_status()

    first_page_soup = BeautifulSoup(response.text, "html.parser")
    page_urls = [url]
    for anchor in first_page_soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin("https://www.sweetmarias.com", href)
        if "green-coffee.html?p=" not in absolute:
            continue
        if absolute not in page_urls:
            page_urls.append(absolute)

    seen_products: set[str] = set()
    for page_url in page_urls[:24]:
        page_response = fetch_with_fallback(page_url, prefer_cloudscraper=True)
        if page_response.status_code >= 400:
            continue

        soup = BeautifulSoup(page_response.text, "html.parser")
        for card in soup.select(".product-item, li.item.product.product-item, .products-grid .item"):
            name_el = card.select_one(".product-item-link")
            price_el = card.select_one(".price-box .price, .special-price .price, .price")
            if not name_el or not price_el:
                continue

            name = name_el.get_text(" ", strip=True)
            href = name_el.get("href")
            if not href or "?" in href or name.startswith("$"):
                continue

            normalized_href = urljoin("https://www.sweetmarias.com", href)
            dedupe_key = f"{name.lower()}::{normalized_href}"
            if dedupe_key in seen_products:
                continue

            price_text = price_el.get_text(" ", strip=True).replace("$", "")
            try:
                price = float(price_text)
            except ValueError:
                continue

            if price <= 0:
                continue

            card_text = card.get_text(" ", strip=True)
            description_el = card.select_one(".product-item-details .description, .description, .short-description")
            description_text = description_el.get_text(" ", strip=True) if description_el else None
            notes = extract_notes_from_text(description_text) or derive_notes_from_name(name, card_text)

            deal = annotate_deal(
                GreenCoffeeDeal(
                    source="Sweet Maria's",
                    name=name,
                    pricePerLb=price,
                    origin=infer_origin_from_title(name),
                    priceText=price_el.get_text(" ", strip=True),
                    productUrl=normalized_href,
                    dealTag="Sale" if "sale" in card.get_text(" ", strip=True).lower() else None,
                    notes=notes,
                )
            )
            deals.append(deal)
            seen_products.add(dedupe_key)

    return deals


def parse_happy_mug() -> list[GreenCoffeeDeal]:
    deals: list[GreenCoffeeDeal] = []
    shopify_json_url = "https://happymugcoffee.com/collections/green-coffee/products.json?limit=250"
    try:
        response = SESSION.get(shopify_json_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()

        for product in payload.get("products", []):
            title = str(product.get("title", "")).strip()
            if not title:
                continue

            tags_raw = product.get("tags", "")
            body_html = product.get("body_html") or None
            notes = (
                extract_happy_mug_notes_from_body_html(body_html)
                or normalize_tag_notes(tags_raw)
                or derive_notes_from_name(title)
            )

            for variant in product.get("variants", []):
                price_raw = variant.get("price")
                try:
                    price = float(price_raw)
                except (TypeError, ValueError):
                    continue

                size = variant.get("title") or None
                weight_lbs = parse_weight_lbs(size)
                price_per_lb = (price / weight_lbs) if weight_lbs and weight_lbs > 0 else price

                deals.append(
                    annotate_deal(
                        GreenCoffeeDeal(
                            source="Happy Mug",
                            name=title,
                            origin=infer_origin_from_title(title),
                            pricePerLb=price_per_lb,
                            size=size,
                            priceText=str(price_raw) if price_raw is not None else None,
                            productUrl=f"https://happymugcoffee.com/products/{product.get('handle')}" if product.get("handle") else None,
                            notes=notes,
                        )
                    )
                )
    except Exception:
        pass

    if deals:
        return deals

    url = "https://happymugcoffee.com/collections/green-coffee"
    response = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for card in soup.select(".product-item, .grid-product, .product, .card-wrapper"):
        name_el = card.select_one("a[href*='/products/']")
        price_el = card.select_one(".price, .money, .price-item")
        if not name_el or not price_el:
            continue

        name = name_el.get_text(" ", strip=True)
        price_text = price_el.get_text(" ", strip=True).replace("$", "")
        try:
            price = float(price_text)
        except ValueError:
            continue

        href = name_el.get("href")
        deal = annotate_deal(
            GreenCoffeeDeal(
                source="Happy Mug",
                name=name,
                pricePerLb=price,
                priceText=price_el.get_text(" ", strip=True),
                productUrl=urljoin("https://happymugcoffee.com", href) if href else None,
            )
        )
        deals.append(deal)

    return deals


def parse_genuine_origin() -> list[GreenCoffeeDeal]:
    deals: list[GreenCoffeeDeal] = []

    listing_url = "https://www.genuineorigin.com/greencoffee"
    listing_response = fetch_with_fallback(listing_url, prefer_cloudscraper=True)
    listing_response.raise_for_status()

    listing_soup = BeautifulSoup(listing_response.text, "html.parser")
    page_urls: list[str] = [listing_url]
    for anchor in listing_soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin("https://www.genuineorigin.com", href)
        if "/greencoffee?page=" not in absolute:
            continue
        if absolute not in page_urls:
            page_urls.append(absolute)

    seen_product_urls: set[str] = set()
    for page_url in page_urls[:12]:
        page_response = fetch_with_fallback(page_url, prefer_cloudscraper=True)
        if page_response.status_code >= 400:
            continue

        page_soup = BeautifulSoup(page_response.text, "html.parser")
        cards = page_soup.select(".facets-item-cell-grid")
        if not cards:
            continue

        for card in cards:
            name_anchor = card.select_one("a.facets-item-cell-grid-title, .facets-item-cell-grid-title a")
            name_node = name_anchor or card.select_one(".facets-item-cell-grid-title")
            if not name_node:
                continue

            name = name_node.get_text(" ", strip=True)
            if not name:
                continue

            href = name_anchor.get("href") if name_anchor else None
            if not href:
                meta_url = card.select_one("meta[itemprop='url']")
                href = meta_url.get("content") if meta_url else None
            product_url = urljoin("https://www.genuineorigin.com", href) if href else None
            if product_url and product_url in seen_product_urls:
                continue

            price_node = card.select_one(".product-views-price-exact, .product-views-price, .cart-quickaddtocart-price")
            price_text_raw = price_node.get_text(" ", strip=True) if price_node else card.get_text(" ", strip=True)
            lb_price_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*/\s*lb", price_text_raw, re.I)
            price = None
            if lb_price_match:
                try:
                    price = float(lb_price_match.group(1))
                except ValueError:
                    price = None

            notes_text = extract_notes_from_text(
                card.select_one(".cart-quickaddtocart-item-flavor").get_text(" ", strip=True)
                if card.select_one(".cart-quickaddtocart-item-flavor")
                else None
            )

            score_value = None
            score_node = card.select_one(".product-details-score")
            if score_node:
                score_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", score_node.get_text(" ", strip=True))
                if score_match:
                    try:
                        score_value = float(score_match.group(1))
                    except ValueError:
                        score_value = None

            deal = annotate_deal(
                GreenCoffeeDeal(
                    source="Genuine Origin",
                    name=name,
                    origin=infer_origin_from_title(name),
                    pricePerLb=price,
                    priceText=lb_price_match.group(0) if lb_price_match else "Unavailable",
                    productUrl=product_url,
                    score=score_value,
                    dealTag="Greencoffee listing",
                    notes=notes_text or derive_notes_from_name(name),
                )
            )
            deals.append(deal)
            if product_url:
                seen_product_urls.add(product_url)

    return deals


def parse_covoya() -> list[GreenCoffeeDeal]:
    deals: list[GreenCoffeeDeal] = []

    fetch_with_fallback("https://www.covoyacoffee.com/")

    page_urls: list[str] = ["https://www.covoyacoffee.com/origins.html"]
    page_urls.extend([f"https://www.covoyacoffee.com/origins.html?p={page}" for page in range(2, 30)])

    seen_product_urls: set[str] = set()
    pages_without_new_rows = 0
    for page_url in page_urls[:24]:
        page_response = fetch_with_fallback(page_url)
        if page_response.status_code >= 400:
            pages_without_new_rows += 1
            if pages_without_new_rows >= 2:
                break
            continue

        page_soup = BeautifulSoup(page_response.text, "html.parser")
        cards = page_soup.select(".item.product.product-item")
        if not cards:
            pages_without_new_rows += 1
            if pages_without_new_rows >= 2:
                break
            continue

        rows_before_page = len(seen_product_urls)

        for card in cards:
            name_el = card.select_one(".product-item-link")
            if not name_el:
                continue

            name = name_el.get_text(" ", strip=True)
            href = (name_el.get("href") or "").strip()
            product_url = urljoin("https://www.covoyacoffee.com", href) if href else None
            if not name or not product_url:
                continue
            if product_url in seen_product_urls:
                continue

            notes = extract_notes_from_text(
                card.select_one(".coffee-icon span").get_text(" ", strip=True)
                if card.select_one(".coffee-icon span")
                else None
            )

            lb_price_text = None
            price_node = card.select_one(".lb-price, .bag-price, .price")
            if price_node:
                lb_price_text = extract_notes_from_text(price_node.get_text(" ", strip=True))

            is_login_locked = bool(card.select_one('a[href*="customer/account/login"]'))

            price_per_lb = None
            normalized_price_text = "Login required" if is_login_locked else None
            deal_tag = "Origins listing"

            if lb_price_text:
                price_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)", lb_price_text)
                if price_match:
                    try:
                        candidate = float(price_match.group(1))
                        if 1.5 <= candidate <= 30:
                            price_per_lb = candidate
                            normalized_price_text = f"${candidate:.2f}"
                            deal_tag = "Origins listing"
                    except ValueError:
                        pass

            deal = annotate_deal(
                GreenCoffeeDeal(
                    source="Covoya",
                    name=name,
                    origin=infer_origin_from_title(name),
                    pricePerLb=price_per_lb,
                    priceText=normalized_price_text,
                    productUrl=product_url,
                    dealTag=deal_tag if price_per_lb is not None else "Login required",
                    notes=notes,
                )
            )
            deals.append(deal)
            seen_product_urls.add(product_url)

        if len(seen_product_urls) == rows_before_page:
            pages_without_new_rows += 1
            if pages_without_new_rows >= 2:
                break
        else:
            pages_without_new_rows = 0

    return deals


def collect_all_deals() -> tuple[list[GreenCoffeeDeal], list[SourceScrapeResult]]:
    all_deals: list[GreenCoffeeDeal] = []
    source_results: list[SourceScrapeResult] = []

    scrapers: Iterable[tuple[str, callable[[], list[GreenCoffeeDeal]]]] = [
        ("Hacea Coffee", parse_hacea),
        ("Sweet Maria's", parse_sweet_marias),
        ("Happy Mug", parse_happy_mug),
        ("Genuine Origin", parse_genuine_origin),
        ("Covoya", parse_covoya),
    ]

    for source_name, scraper in scrapers:
        started_at = perf_counter()
        try:
            source_deals = scraper()
            all_deals.extend(source_deals)
            duration_ms = int((perf_counter() - started_at) * 1000)
            status = "ok" if source_deals else "no-data"
            source_results.append(
                SourceScrapeResult(
                    source=source_name,
                    status=status,
                    dealsCollected=len(source_deals),
                    durationMs=duration_ms,
                    error=None,
                )
            )
            print(f"[{source_name}] collected {len(source_deals)} deals")
        except Exception as error:
            duration_ms = int((perf_counter() - started_at) * 1000)
            source_results.append(
                SourceScrapeResult(
                    source=source_name,
                    status="error",
                    dealsCollected=0,
                    durationMs=duration_ms,
                    error=str(error),
                )
            )
            print(f"[{source_name}] failed: {error}")

    return all_deals, source_results


def write_cache(deals: list[GreenCoffeeDeal], source_results: list[SourceScrapeResult]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    successful_sources = sum(1 for result in source_results if result.status in {"ok", "no-data"})
    failed_sources = sum(1 for result in source_results if result.status == "error")
    payload = {
        "generatedAt": now_iso(),
        "lastUpdated": now_iso(),
        "deals": [asdict(deal) for deal in deals],
        "scrapeReport": {
            "sources": [asdict(result) for result in source_results],
            "successfulSources": successful_sources,
            "failedSources": failed_sources,
            "totalDeals": len(deals),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    deals, source_results = collect_all_deals()
    deals.sort(key=lambda item: item.pricePerLb if Number_isfinite(item.pricePerLb) else float("inf"))
    write_cache(deals, source_results)
    print(f"Saved {len(deals)} deals to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
