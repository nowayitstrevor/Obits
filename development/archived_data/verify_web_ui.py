"""
Quick verification of what the web UI API will return.
"""

import json
import os
from enhanced_web_ui import load_config, load_obituaries_from_storage

def verify_web_ui_data():
    print("=== Web UI Data Verification ===")
    
    # Simulate what the updated /api/obituaries endpoint does
    config = load_config()
    all_obituaries = []
    
    # Load from detailed scraper file first
    detailed_file = 'obituaries_all_detailed.json'
    if os.path.exists(detailed_file):
        detailed_obituaries = load_obituaries_from_storage(detailed_file)
        all_obituaries.extend(detailed_obituaries)
        print(f"✅ Loaded {len(detailed_obituaries)} obituaries from detailed scraper")
    else:
        print("❌ No detailed scraper file found")
    
    # Load from individual files (as supplement)
    individual_count = 0
    for home_id, home_info in config.get('funeral_homes', {}).items():
        if not home_info.get('active', False):
            continue
            
        storage_file = home_info['storage_file']
        if os.path.exists(storage_file):
            obituaries = load_obituaries_from_storage(storage_file, home_info['name'])
            
            # Only add obituaries that aren't already in the detailed list
            existing_urls = {obit.get('url', '') for obit in all_obituaries}
            new_obituaries = [obit for obit in obituaries if obit.get('url', '') not in existing_urls]
            
            if new_obituaries:
                all_obituaries.extend(new_obituaries)
                individual_count += len(new_obituaries)
                print(f"✅ Added {len(new_obituaries)} new obituaries from {home_info['name']}")
    
    if individual_count > 0:
        print(f"✅ Total additional from individual files: {individual_count}")
    else:
        print("ℹ️  No additional obituaries from individual files (all already in detailed)")
    
    # Final summary
    print(f"\n🎯 TOTAL OBITUARIES AVAILABLE IN WEB UI: {len(all_obituaries)}")
    
    # Breakdown by funeral home
    funeral_homes = {}
    for obit in all_obituaries:
        fh = obit.get('funeral_home', 'Unknown')
        funeral_homes[fh] = funeral_homes.get(fh, 0) + 1
    
    print("\n📊 Breakdown by Funeral Home:")
    for fh, count in sorted(funeral_homes.items()):
        print(f"   {fh}: {count} obituaries")
    
    return len(all_obituaries)

if __name__ == "__main__":
    total = verify_web_ui_data()
    print(f"\n{'='*50}")
    print(f"🚀 Your web UI should now display {total} obituaries!")
    print(f"{'='*50}")
