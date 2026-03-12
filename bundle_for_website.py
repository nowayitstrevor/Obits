#!/usr/bin/env python3
"""
Bundle all working funeral home obituaries for the website
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

SELECTED_SCRAPE_OUTPUT = 'obituaries_selected_pages.json'
LOOKBACK_DAYS = 14
EXCLUDED_FUNERAL_HOMES = set()
NOISY_URL_MARKERS = (
    "/send-flowers",
    "/sympathy",
    "/obituary-listings",
    "/obituary-resources",
    "/obituary-writer",
)
NOISY_TEXT_MARKERS = (
    "this site is protected by recaptcha",
    "please ensure javascript is enabled",
    "we would like to offer our sincere support to anyone coping with grief",
    "enter your phone number above to have directions sent via text",
)


def parse_flexible_date(value: Any):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return None

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def should_drop_obituary(obit: Dict[str, Any], home_name: str) -> bool:
    if home_name in EXCLUDED_FUNERAL_HOMES:
        return True

    name = str(obit.get("name") or "").lower()
    url = str(obit.get("url") or "").lower()

    if any(marker in url for marker in NOISY_URL_MARKERS):
        return True

    if "obituary listings" in name or "obituary resources" in name or "obituary writer" in name:
        return True

    return False


def is_within_lookback(obit: Dict[str, Any], lookback_days: int = LOOKBACK_DAYS) -> bool:
    if lookback_days <= 0:
        return True

    death_value = obit.get("date_of_death", obit.get("death_date"))
    parsed = parse_flexible_date(death_value)
    if parsed is None:
        return False

    cutoff = datetime.now() - timedelta(days=lookback_days)
    return parsed >= cutoff

def load_existing_obituaries() -> Dict[str, List[Dict]]:
    """Load obituaries from all working funeral homes."""
    
    print("📊 Loading existing obituaries from working funeral homes...")
    print("=" * 60)
    
    obituaries_by_home = {}
    
    # Working funeral homes based on actual files and analysis
    working_homes = {
        "Foss Funeral Home": "obituaries_fossfuneralhome.json",
        "McDowell Funeral Home": "obituaries_mcdowellfuneralhome.json", 
        "Bellmead Funeral Home": "obituaries_bellmead.json",
        "SLC Texas Funeral Services": "obituaries_slctx.json"
    }
    
    total_count = 0
    
    for home_name, filename in working_homes.items():
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    
                    # Handle nested structure - extract obituaries from the "obituaries" key
                    if isinstance(file_data, dict) and "obituaries" in file_data:
                        obituaries_dict = file_data["obituaries"]
                        # Convert from dict of dicts to list of dicts
                        obituaries_list = list(obituaries_dict.values())
                    elif isinstance(file_data, list):
                        obituaries_list = file_data
                    else:
                        obituaries_list = []
                    
                    obituaries_by_home[home_name] = obituaries_list
                    count = len(obituaries_list)
                    total_count += count
                    print(f"  ✅ {home_name}: {count} obituaries")
            except Exception as e:
                print(f"  ❌ Error loading {filename}: {e}")
                obituaries_by_home[home_name] = []
        else:
            print(f"  ⚠️  {filename} not found")
            obituaries_by_home[home_name] = []
    
    print(f"\n📈 Total existing obituaries: {total_count}")
    return obituaries_by_home

def add_grace_gardens_obituaries() -> List[Dict]:
    """Add the Grace Gardens obituaries we extracted."""
    
    print("\n🌺 Adding Grace Gardens obituaries...")
    print("=" * 40)
    
    # Grace Gardens obituaries from our analysis
    grace_gardens_obituaries = [
        {
            "name": "Vernon Eugene Hoppe",
            "url": "https://www.gracegardensfh.com/obituaries/vernon-hoppe",
            "date_of_death": "July 21, 2025",
            "summary": "Vernon Eugene Hoppe (Gene) of Woodway, went home to Heaven on Monday, July 21, 2025 at the age of 91. Funeral services will be Saturday, July 26 at 11:00 at St. Paul Lutheran Church of Crawford with Pastor Ricky Richards officiating. Visitation with the family will be the hour prior to the service beginning at 10:00. Burial will immediately follow at St. Paul Lutheran Memorial Park. Gene was born on November 21, 1933, to the late Alfred and Anna (Sandhoff) Hoppe.",
            "photo_url": "https://cdn.tukioswebsites.com/2726b75f-2f30-461d-a820-cd07e37be195/md",
            "age": "91",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "November 21, 1933",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Peggy Shelton",
            "url": "https://www.gracegardensfh.com/obituaries/peggy-shelton",
            "date_of_death": "July 18, 2025",
            "summary": "Peggy Gene Felder Shelton, aged 87, of Waco, Texas, passed away on Friday, July 18, 2025. Born in Taylor, Texas on February 28, 1938, to Eddie Felder and Annie Maresh, Peggy was raised in Austin, Texas. She married Ronnie Shelton on December 11, 1954, and together they raised three daughters. Throughout her career, Peggy held various retail positions, including roles at Texas Gold Stamps and Yarings. She was an active member of Redeemer Lutheran Church in Austin before relocating with her family to Waco.",
            "photo_url": "https://cdn.tukioswebsites.com/91d3a9e7-1d43-461d-8b21-316e345f4ecb/md",
            "age": "87",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "February 28, 1938",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Billy F. Spivey",
            "url": "https://www.gracegardensfh.com/obituaries/billy-spivey",
            "date_of_death": "July 22, 2025",
            "summary": "Billy F. Spivey of Woodway, Texas passed away on July 22, 2025. A visitation in his honor will be on Thursday, July 31, 2025 from 5:00pm to 7:00pm at Grace Gardens Funeral Home in Woodway, Texas. A celebration of life service will be at 11:00am, Friday, August 1, 2025 at Grace Gardens Funeral Home with burial following at Powers Chapel Cemetery in Rosebud, Texas. A full obituary is forthcoming.",
            "photo_url": "https://cdn.tukioswebsites.com/34c29740-6a6a-4ab2-acb6-9a539f19df72/md",
            "age": "Unknown",
            "funeral_home": "Grace Gardens Funeral Home",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Robert (Rob) Dale Green",
            "url": "https://www.gracegardensfh.com/obituaries/robert-green",
            "date_of_death": "May 26, 2025",
            "summary": "Robert Dale Green, beloved husband, father, brother, son, and friend, passed away peacefully with his family by his side on May 26, 2025, in Waco, Texas. Born on May 30, 1968, Rob spent his early childhood growing up with his family, grandparents and a large extended family in Michigan. Rob then moved with his family to San Diego, California in 1980. After working in construction for several years following high school, Rob obtained his degree in Graphic Arts and began a successful career in printing and marketing.",
            "photo_url": "https://cdn.tukioswebsites.com/47fc4a8e-3f62-4181-9bb8-3f8b8307a11a/md",
            "age": "57",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "May 30, 1968",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Kathleen Lindsey",
            "url": "https://www.gracegardensfh.com/obituaries/kathleen-lindsey",
            "date_of_death": "July 15, 2025",
            "summary": "Kathleen Mayr Lindsey—beloved wife, mother, grandmother, daughter, sister, aunt, and friend—passed away peacefully in Richardson, Texas on July 15, 2025. She was 74 years old. A Celebration of Life service will be held in her honor at McGregor Baptist Church on August 9, 2025, at 11:00 AM. Kathleen was born in Waco, Texas, on January 5, 1951, to Charles and Burnell Mayr. She was the second of three children. The family made their home in Waco, where Kathleen graduated from Waco High School.",
            "photo_url": "https://cdn.tukioswebsites.com/ec740759-ca3d-4709-8e5e-7b7a3912d4e7/md",
            "age": "74",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "January 5, 1951",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "James Daniel Speasmaker",
            "url": "https://www.gracegardensfh.com/obituaries/james-speasmaker",
            "date_of_death": "July 6, 2025",
            "summary": "James Daniel Speasmaker, 50, loving husband and father, passed away on July 6, 2025. A Visitation in his honor will be on Monday, July 14, 2025 from 5:00pm to 7:00pm. A Funeral Service will be at 11:00am, Tuesday, July 15, 2025, at Grace Gardens. James was born in Rota, Cádiz, Spain, on September 23, 1974. A 1992 graduate of LaVega High School, James went on to serve in the U. S. Navy for four years before becoming valedictorian of his Fire Academy class.",
            "photo_url": "https://cdn.tukioswebsites.com/858fa3ff-d2e6-44eb-9cdf-7de5cb175ecf/md",
            "age": "50",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "September 23, 1974",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Charles Alfred Knox",
            "url": "https://www.gracegardensfh.com/obituaries/charles-knox",
            "date_of_death": "July 18, 2025",
            "summary": "Charles A. Knox passed away peacefully on July 18, 2025, at Baylor Scott & White Hillcrest Hospital in Waco, Texas. He was born on September 19, 1930, in Marion, Ohio, to Charles E. Knox and Garnet Everly Knox. Charles served his country in the United States Air Force for over 20 years, with assignments that took him to Vietnam, Greenland, Saudi Arabia, and Labrador. While stationed at James Connally Air Force Base in Waco, Charles met and married Erline Hamilton on October 3, 1959.",
            "photo_url": "https://cdn.tukioswebsites.com/6e4f09b2-9a43-45b4-b6cb-522b191fd193/md",
            "age": "95",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "September 19, 1930",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Douglas Wade Smith, Sr.",
            "url": "https://www.gracegardensfh.com/obituaries/douglas-smith-sr",
            "date_of_death": "July 12, 2025",
            "summary": "Douglas Wade Smith went to join our Lord and supreme master on July 12, 2025, after a lengthy illness. He died at home surrounded by loved ones. Douglas was born August 18, 1941, to Ophelia and Bee Smith in Pancake, Texas. He joined the Marine Corps in 1959 then returned to Waco, Texas and worked at Waco Meat Service where he made many lifelong friends. Douglas is past master of Fidelis 1127 FM/AM lodge, past Worthy patron of Walter Baldwin EOS chapter.",
            "photo_url": "https://cdn.tukioswebsites.com/0b6314e4-1a90-4739-a2e5-4ebd75b1af72/md",
            "age": "84",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "August 18, 1941",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Michael Ray Townsend",
            "url": "https://www.gracegardensfh.com/obituaries/michael-townsend",
            "date_of_death": "July 11, 2025",
            "summary": "Michael Ray Townsend, born on July 3, 1946, in Waco, Texas, passed away peacefully on July 11, 2025, in Hewitt, Texas, surrounded by his loved ones. A dedicated free spirit, he enjoyed a life filled with adventure and exploration, becoming a long-haul truck driver who relished the open road. Michael's passion for travel was complemented by his love for the outdoors, fishing, and animals, reflecting his vibrant personality and zest for life.",
            "photo_url": "https://cdn.tukioswebsites.com/f2c13998-ad9e-49a4-a755-eb5a303a1c40/md",
            "age": "79",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "July 3, 1946",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "name": "Omadath Adesh Ramdhansingh",
            "url": "https://www.gracegardensfh.com/obituaries/omadath-adesh-ramdhansingh",
            "date_of_death": "July 10, 2025",
            "summary": "Omadath \"Adesh\" Ramdhansingh, 49, passed away on July 10, 2025, in Dallas, Texas, surrounded by his loved ones. Born on August 1, 1975, in San Fernando, Trinidad, Adesh's early years were filled with the warmth of close family and cherished friendships. Though life brought its share of hardships, Adesh lived by his personal motto: to live life to the fullest. Rarely seen without a smile or a joke, he brought light and laughter to those around him.",
            "photo_url": "https://cdn.tukioswebsites.com/bde32937-2d16-4613-9abe-f2d9d6066cc5/md",
            "age": "49",
            "funeral_home": "Grace Gardens Funeral Home",
            "birth_date": "August 1, 1975",
            "scraped_at": datetime.now().isoformat()
        }
    ]
    
    print(f"  ✅ Added {len(grace_gardens_obituaries)} Grace Gardens obituaries")
    return grace_gardens_obituaries

def load_selected_scraped_obituaries() -> Dict[str, List[Dict]]:
    """Load obituaries produced by scrape_selected_obituaries.py if available."""
    if not os.path.exists(SELECTED_SCRAPE_OUTPUT):
        print(f"\nℹ️  {SELECTED_SCRAPE_OUTPUT} not found; continuing with existing data")
        return {}

    print(f"\n🧩 Loading {SELECTED_SCRAPE_OUTPUT}...")
    print("=" * 40)

    try:
        with open(SELECTED_SCRAPE_OUTPUT, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception as e:
        print(f"  ❌ Error reading {SELECTED_SCRAPE_OUTPUT}: {e}")
        return {}

    grouped: Dict[str, List[Dict]] = {}
    for record in payload.get("obituaries", []):
        home_name = record.get("sourceName") or record.get("sourceKey") or "Unknown"
        mapped = {
            "name": record.get("name"),
            "url": record.get("obituaryUrl"),
            "birth_date": record.get("birthDate"),
            "death_date": record.get("deathDate"),
            "age": record.get("age"),
            "summary": record.get("summary"),
            "photo_url": record.get("photoUrl"),
            "funeral_home": home_name,
            "scraped_at": record.get("scrapedAt", datetime.now().isoformat())
        }
        grouped.setdefault(home_name, []).append(mapped)

    total = sum(len(v) for v in grouped.values())
    print(f"  ✅ Loaded {total} obituaries from {len(grouped)} sources")
    return grouped

def create_unified_dataset():
    """Create a unified dataset of all obituaries for the website."""
    
    print("\n🌐 Creating unified dataset for website...")
    print("=" * 50)
    
    # Load existing obituaries
    existing_obituaries = load_existing_obituaries()
    
    # Add Grace Gardens obituaries
    grace_gardens_obits = add_grace_gardens_obituaries()
    existing_obituaries["Grace Gardens Funeral Home"] = grace_gardens_obits

    # Merge scraper output from selected pages (if present)
    selected_obits = load_selected_scraped_obituaries()
    for home_name, records in selected_obits.items():
        existing_obituaries.setdefault(home_name, [])
        existing_obituaries[home_name].extend(records)
    
    # Create unified list
    all_obituaries = []
    funeral_home_stats = {}
    seen_urls = set()
    
    for home_name, obituaries in existing_obituaries.items():
        count = 0
        
        for obit in obituaries:
            if should_drop_obituary(obit, home_name):
                continue
            if not is_within_lookback(obit):
                continue

            url = obit.get("url", "")
            dedupe_key = url.strip().lower() if isinstance(url, str) else ""
            if dedupe_key and dedupe_key in seen_urls:
                continue
            if dedupe_key:
                seen_urls.add(dedupe_key)

            count += 1

            # Ensure all obituaries have required fields
            unified_obit = {
                "id": len(all_obituaries) + 1,
                "name": obit.get("name", "Unknown"),
                "funeral_home": home_name,
                "date_of_death": obit.get("date_of_death", obit.get("death_date", "Unknown")),
                "birth_date": obit.get("birth_date", None),
                "age": obit.get("age", "Unknown"),
                "summary": obit.get("summary", obit.get("content", "")),
                "photo_url": obit.get("photo_url", ""),
                "url": obit.get("url", ""),
                "scraped_at": obit.get("scraped_at", datetime.now().isoformat()),
                "service_info": obit.get("service_info", None)
            }
            all_obituaries.append(unified_obit)

        funeral_home_stats[home_name] = count
    
    # Sort by date of death (most recent first)
    all_obituaries.sort(
        key=lambda item: (
            parse_flexible_date(item.get("date_of_death")) or datetime.min,
            str(item.get("name") or "")
        ),
        reverse=True,
    )

    # Re-assign IDs after filtering/sorting
    for index, obituary in enumerate(all_obituaries, start=1):
        obituary["id"] = index
    
    # Create summary statistics
    active_funeral_home_stats = {home: count for home, count in funeral_home_stats.items() if count > 0}

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_obituaries": len(all_obituaries),
        "funeral_homes": active_funeral_home_stats,
        "working_funeral_homes": len(active_funeral_home_stats)
    }
    
    # Create final dataset
    website_data = {
        "summary": summary,
        "obituaries": all_obituaries
    }
    
    # Save main dataset
    with open('website_obituaries.json', 'w', encoding='utf-8') as f:
        json.dump(website_data, f, indent=2, ensure_ascii=False)
    
    # Save obituaries-only file (for easier website integration)
    with open('obituaries_for_website.json', 'w', encoding='utf-8') as f:
        json.dump(all_obituaries, f, indent=2, ensure_ascii=False)
    
    # Save Grace Gardens to its proper file
    with open('obituaries_gracegardens.json', 'w', encoding='utf-8') as f:
        json.dump(grace_gardens_obits, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 WEBSITE DATASET SUMMARY:")
    print(f"  📋 Total obituaries: {len(all_obituaries)}")
    print(f"  🏠 Working funeral homes: {len([h for h, c in funeral_home_stats.items() if c > 0])}")
    print(f"\n📈 OBITUARIES BY FUNERAL HOME:")
    
    for home_name, count in sorted(funeral_home_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"    ✅ {home_name}: {count} obituaries")
    
    print(f"\n💾 FILES CREATED:")
    print(f"    📄 website_obituaries.json - Complete dataset with metadata")
    print(f"    📄 obituaries_for_website.json - Obituaries only (for website)")
    print(f"    📄 obituaries_gracegardens.json - Grace Gardens specific file")
    
    print(f"\n🎉 SUCCESS! Website dataset ready with {len(all_obituaries)} obituaries!")
    
    return website_data

if __name__ == "__main__":
    create_unified_dataset()
