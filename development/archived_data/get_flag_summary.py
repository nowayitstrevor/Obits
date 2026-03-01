#!/usr/bin/env python3
"""
Get a summary of remaining unresolved flags.
"""

import json

def get_flag_summary():
    """Get summary of all unresolved flags."""
    
    with open('obituary_flags.json', 'r') as f:
        flags_data = json.load(f)
    
    unresolved_flags = []
    
    for flag_key, flag_info in flags_data.items():
        for flag in flag_info['flags']:
            if not flag.get('resolved', False):
                unresolved_flags.append({
                    'url': flag_info['obituary_url'],
                    'funeral_home': flag_info['funeral_home'],
                    'type': flag['type'],
                    'notes': flag.get('notes', '')
                })
    
    print(f"Total unresolved flags: {len(unresolved_flags)}\n")
    
    # Group by type
    by_type = {}
    for flag in unresolved_flags:
        flag_type = flag['type']
        if flag_type not in by_type:
            by_type[flag_type] = []
        by_type[flag_type].append(flag)
    
    for flag_type, flags in by_type.items():
        print(f"{flag_type.upper()}: {len(flags)} flags")
        for flag in flags:
            print(f"  - {flag['funeral_home']}: {flag['url']}")
        print()

if __name__ == "__main__":
    get_flag_summary()
