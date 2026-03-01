#!/usr/bin/env python3
"""
Analyze which funeral homes are successfully populating obituaries and which need attention.
"""

import json
from collections import defaultdict

def analyze_funeral_home_population():
    """Analyze obituary population by funeral home."""
    
    # Load current obituary data
    with open('obituaries_all_detailed.json', 'r', encoding='utf-8') as f:
        obituaries = json.load(f)
    
    # Load configuration to get all funeral homes
    with open('funeral_homes_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Count obituaries by funeral home
    obituary_counts = defaultdict(int)
    for obit in obituaries:
        funeral_home = obit.get('funeral_home', 'Unknown')
        obituary_counts[funeral_home] += 1
    
    # Get all configured funeral homes
    configured_homes = {}
    for key, home_config in config['funeral_homes'].items():
        configured_homes[home_config['name']] = {
            'url': home_config['url'],
            'active': home_config.get('active', True),
            'scraper_type': home_config.get('scraper_type', 'unknown'),
            'last_scraped': home_config.get('last_scraped', 'Never'),
            'config_key': key
        }
    
    print("🏠 FUNERAL HOME POPULATION ANALYSIS")
    print("=" * 60)
    
    # Show populated homes (working)
    print("\n✅ WORKING FUNERAL HOMES:")
    working_homes = []
    for home_name, count in sorted(obituary_counts.items()):
        if count > 0:
            config_info = configured_homes.get(home_name, {})
            print(f"  📊 {home_name}: {count} obituaries")
            if config_info:
                print(f"      URL: {config_info.get('url', 'Unknown')}")
                print(f"      Type: {config_info.get('scraper_type', 'Unknown')}")
            working_homes.append(home_name)
    
    # Show non-populated homes (need attention)
    print(f"\n❌ FUNERAL HOMES NEEDING ATTENTION:")
    problem_homes = []
    for home_name, config_info in configured_homes.items():
        if config_info['active'] and home_name not in obituary_counts:
            print(f"  🚨 {home_name}: 0 obituaries")
            print(f"      URL: {config_info['url']}")
            print(f"      Type: {config_info['scraper_type']}")
            print(f"      Config Key: {config_info['config_key']}")
            print(f"      Last Scraped: {config_info['last_scraped']}")
            problem_homes.append({
                'name': home_name,
                'url': config_info['url'],
                'type': config_info['scraper_type'],
                'key': config_info['config_key']
            })
    
    print(f"\n📈 SUMMARY:")
    print(f"  ✅ Working funeral homes: {len(working_homes)}")
    print(f"  ❌ Problem funeral homes: {len(problem_homes)}")
    print(f"  📊 Total obituaries: {len(obituaries)}")
    
    if problem_homes:
        print(f"\n🎯 NEXT STEPS - Let's fix these one by one:")
        for i, home in enumerate(problem_homes, 1):
            print(f"  {i}. {home['name']} ({home['type']}) - {home['url']}")
    
    return working_homes, problem_homes

if __name__ == "__main__":
    analyze_funeral_home_population()
