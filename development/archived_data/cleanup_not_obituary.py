#!/usr/bin/env python3
"""
Clean up NOT_OBITUARY flagged entries and resolve the flags.
"""

import json
from datetime import datetime

def cleanup_not_obituary_flags():
    """Remove NOT_OBITUARY flagged entries and resolve flags."""
    
    # Load current data
    with open('obituaries_all_detailed.json', 'r', encoding='utf-8') as f:
        obituaries = json.load(f)
    
    with open('obituary_flags.json', 'r', encoding='utf-8') as f:
        flags_data = json.load(f)
    
    # Identify NOT_OBITUARY URLs to remove
    urls_to_remove = set()
    
    for flag_key, flag_info in flags_data.items():
        for flag in flag_info['flags']:
            if flag['type'] == 'not_obituary' and not flag.get('resolved', False):
                urls_to_remove.add(flag_info['obituary_url'])
                print(f"🗑️  Will remove: {flag_info['obituary_url']}")
    
    print(f"\nFound {len(urls_to_remove)} NOT_OBITUARY URLs to remove")
    
    # Remove the problematic entries from obituaries
    original_count = len(obituaries)
    obituaries = [obit for obit in obituaries if obit['url'] not in urls_to_remove]
    removed_count = original_count - len(obituaries)
    
    print(f"✅ Removed {removed_count} invalid obituary entries")
    print(f"📊 Obituaries: {original_count} → {len(obituaries)}")
    
    # Resolve the flags
    resolved_count = 0
    for flag_key, flag_info in flags_data.items():
        if flag_info['obituary_url'] in urls_to_remove:
            for flag in flag_info['flags']:
                if flag['type'] == 'not_obituary' and not flag.get('resolved', False):
                    flag['resolved'] = True
                    flag['resolved_at'] = datetime.now().isoformat()
                    flag['resolution_reason'] = "Invalid obituary entry removed from data"
                    flag_info['updated_at'] = datetime.now().isoformat()
                    resolved_count += 1
    
    # Also resolve any INCOMPLETE_CONTENT flags for send-flowers pages
    for flag_key, flag_info in flags_data.items():
        if '/send-flowers' in flag_info['obituary_url']:
            for flag in flag_info['flags']:
                if flag['type'] == 'incomplete_content' and not flag.get('resolved', False):
                    flag['resolved'] = True
                    flag['resolved_at'] = datetime.now().isoformat()
                    flag['resolution_reason'] = "Send-flowers page should not be scraped as obituary"
                    flag_info['updated_at'] = datetime.now().isoformat()
                    resolved_count += 1
                    print(f"✅ RESOLVED: incomplete_content for send-flowers page: {flag_info['obituary_url']}")
    
    # Save updated data
    with open('obituaries_all_detailed.json', 'w', encoding='utf-8') as f:
        json.dump(obituaries, f, indent=2, ensure_ascii=False)
    
    with open('obituary_flags.json', 'w', encoding='utf-8') as f:
        json.dump(flags_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Cleanup complete!")
    print(f"✅ Resolved {resolved_count} flags")
    print(f"💾 Updated obituaries_all_detailed.json and obituary_flags.json")
    
    return removed_count, resolved_count

if __name__ == "__main__":
    cleanup_not_obituary_flags()
